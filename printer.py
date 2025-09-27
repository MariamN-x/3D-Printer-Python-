import simpy
import random
from ecu import ECU
from actuator import Actuator
from sensor import Sensor
from utils import log_event
import re

class CyberPhysicalPrinter:
    def __init__(self, env,logger=None):
        self.env = env
        self.logger=logger 
        
        self.print_head = Actuator(env, "Print_Head", 1)
        self.heated_bed = Actuator(env, "Heated_Bed", 1)
        self.steppers = Actuator(env, "Steppers", 3)

        self.main_ecu = ECU(env, "Main_ECU")
        self.motion_ecu = ECU(env, "Motion_ECU")
        self.thermal_ecu = ECU(env, "Thermal_ECU")

        # bus & resources
        self.can_bus = simpy.Store(env)
        self.filament = simpy.Container(env, init=1000, capacity=1000)
        self.power = simpy.PreemptiveResource(env, capacity=1)

        # NEW: Added printer_resource to coordinate downtime/cleaning with printing
        self.printer_resource = simpy.Resource(env, capacity=1)

        self.event_log = []
        
        # NEW: Position tracking for visualization
        self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'E': 0.0}
        self.visualizer = None  # Will be set by main script
        self.relative_positioning = False  # G90/G91 mode

        # sensors
        hotend_sensor = Sensor(env, "Hotend_Thermistor", 0.1, lambda: self.print_head.current_temp)
        bed_sensor = Sensor(env, "Bed_Thermistor", 0.1, lambda: self.heated_bed.current_temp)

        env.process(hotend_sensor.run(self.can_bus, self.event_log))
        env.process(bed_sensor.run(self.can_bus, self.event_log))
        env.process(self.sensor_filament())

        # NEW: Start maintenance (downtime/cleaning) process
        env.process(self.maintenance_cycle())
        env.process(self._thermal_control_loop())
    def set_visualizer(self, visualizer):
        self.visualizer = visualizer

    def sensor_filament(self):
        while True:
            yield self.env.timeout(1)
            if self.filament.level <= 0:
                self.main_ecu.set_state("ERROR", self.event_log)
                log_event(self.event_log, self.env, "Filament_Sensor", "FAULT",
                            {"msg": "Filament runout"})
                break

    # Maintenance/downtime/cleaning cycle
    def maintenance_cycle(self):
        while True:
            yield self.env.timeout(500 * 60 * 60)  # every 500 hours
            log_event(self.event_log, self.env, "Maintenance", "START", {"msg": "Scheduled cleaning/maintenance"})
            self.main_ecu.set_state("MAINTENANCE", self.event_log)

            # Block the printer for cleaning time (e.g., 20 minutes)
            cleaning_time = 20 * 60  # 20 minutes in seconds
            with self.printer_resource.request() as req:
                yield req
                yield self.env.timeout(cleaning_time)

            log_event(self.event_log, self.env, "Maintenance", "END", {"msg": "Maintenance complete"})
            self.main_ecu.set_state("IDLE", self.event_log)

    # MODIFIED: Wrap print job in printer_resource so print & cleaning can't overlap
    def _print_loop(self, gcode_commands):
        with self.printer_resource.request() as req:
            yield req
            for cmd in gcode_commands:
                yield self.env.process(self._execute_command(cmd))

    def _execute_command(self, gcode):
        with self.main_ecu.resource.request() as req:
            yield req
            self.main_ecu.set_state("PROCESSING", self.event_log)
            yield self.env.timeout(random.uniform(0.001, 0.005))

            if gcode.startswith("G1") or gcode.startswith("G0"):
                # Parse movement parameters
                params = self._parse_gcode_parameters(gcode)
                move_time = self._calculate_move_time(params)
                
                with self.motion_ecu.resource.request() as mreq:
                    yield mreq
                    self.motion_ecu.set_state("MOVING", self.event_log)
                    
                    old_position = self.current_position.copy()
                    yield from self._update_position(params)
                    
                    # Calculate movement type (rapid vs print)
                    movement_type = "RAPID" if gcode.startswith("G0") else "PRINT"
                    if self.visualizer:
                        self.visualizer.update_position(
                            self.current_position['X'],
                            self.current_position['Y'],
                            self.current_position['Z'],
                            movement_type
                        )
                    
                    yield self.env.timeout(move_time)
                    self.motion_ecu.set_state("IDLE", self.event_log)
                    
                    log_event(self.event_log, self.env, "Motion_ECU", "cmd_sent",
                              {"command": gcode, "move_time": move_time,
                               "from": old_position, "to": self.current_position})

            elif gcode.startswith("M104"):
                temp = self._parse_temperature(gcode)
                self.print_head.target_temp = temp
                log_event(self.event_log, self.env, "Thermal_ECU", "SET_TARGET",
                          {"hotend_target": self.print_head.target_temp})

            elif gcode.startswith("M140"):
                temp = self._parse_temperature(gcode)
                self.heated_bed.target_temp = temp
                log_event(self.event_log, self.env, "Thermal_ECU", "SET_TARGET",
                          {"bed_target": self.heated_bed.target_temp})

            elif gcode.startswith("G4"):
                dwell_time = self._parse_dwell_time(gcode)
                yield self.env.timeout(dwell_time)
                log_event(self.event_log, self.env, "Main_ECU", "DWELL",
                          {"command": gcode, "duration": dwell_time})

            elif gcode.startswith("G90"):
                self.relative_positioning = False
                log_event(self.event_log, self.env, "Motion_ECU", "MODE_CHANGE", {"mode": "Absolute positioning"})

            elif gcode.startswith("G91"):
                self.relative_positioning = True
                log_event(self.event_log, self.env, "Motion_ECU", "MODE_CHANGE", {"mode": "Relative positioning"})

            elif gcode.startswith("G28"):
                # Home all axes
                self.current_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'E': 0.0}
                log_event(self.event_log, self.env, "Motion_ECU", "HOMING", {"command": gcode})
                yield self.env.timeout(2.0)

            elif gcode.startswith("G92"):
                # Set position
                params = self._parse_gcode_parameters(gcode)
                for axis in ['X', 'Y', 'Z', 'E']:
                    if axis in params:
                        self.current_position[axis] = params[axis]
                log_event(self.event_log, self.env, "Motion_ECU", "SET_POSITION",
                          {"position": self.current_position})

            self.main_ecu.set_state("IDLE", self.event_log)

    def _parse_gcode_parameters(self, gcode):
        """Parse G-code parameters into a dictionary"""
        params = {}
        pattern = r'([XYZEF])([+-]?\d*\.?\d+)'
        matches = re.findall(pattern, gcode)
        
        for axis, value in matches:
            if value:  # Only add if value is not empty
                params[axis] = float(value)
        
        return params

    def _update_position(self, params):
        """Update position and consume filament if extrusion is involved"""
        for axis in params:
            if axis in self.current_position:
                if axis == 'E':
                    delta_e = params['E'] if self.relative_positioning else params['E'] - self.current_position['E']
                    delta_e = max(0, delta_e)

                    if delta_e > 0:
                        if self.filament.level >= delta_e:
                            yield self.filament.get(delta_e)
                        else:
                            delta_e = self.filament.level
                            yield self.filament.get(delta_e)
                            self.main_ecu.set_state("ERROR", self.event_log)
                            log_event(self.event_log, self.env, "Filament", "FAULT",
                                      {"msg": "Filament runout"})

                    if self.relative_positioning:
                        self.current_position['E'] += delta_e
                    else:
                        self.current_position['E'] = params['E']
                else:
                    if self.relative_positioning:
                        self.current_position[axis] += params[axis]
                    else:
                        self.current_position[axis] = params[axis]

    def _calculate_move_time(self, params):
        """Calculate move time based on distance and feedrate"""
        # Simple implementation - you can enhance this with actual feedrate calculation
        base_time = 0.5
        distance = 0
        
        # Calculate approximate distance for time scaling
        for axis in ['X', 'Y', 'Z']:
            if axis in params:
                if self.relative_positioning:
                    distance += abs(params[axis])
                else:
                    distance += abs(params[axis] - self.current_position.get(axis, 0))
        
        # Scale time based on distance (min 0.1s, max 2.0s)
        extrusion = 0
        if 'E' in params:
            extrusion = params['E'] if self.relative_positioning else params['E'] - self.current_position['E']
        extrusion_time = 0.1 * extrusion if extrusion > 0 else 0
        move_time = max(0.1, min(2.0, base_time * (distance / 10.0) + extrusion_time))        
        return move_time

    def _parse_temperature(self, gcode):
        pattern = r'S(\d+)'
        match = re.search(pattern, gcode)
        return float(match.group(1)) if match else (200 if 'M104' in gcode else 60)

    def _parse_dwell_time(self, gcode):
        pattern = r'P(\d+\.?\d*)'
        match = re.search(pattern, gcode)
        return float(match.group(1)) if match else 1.0

    def _thermal_control_loop(self):
        while True:
            yield self.env.timeout(0.1)
            if self.print_head.current_temp < self.print_head.target_temp - 1:
                self.thermal_ecu.set_state("HEATING", self.event_log)
            else:
                self.thermal_ecu.set_state("IDLE", self.event_log)
            self.print_head.current_temp += (self.print_head.target_temp - self.print_head.current_temp) * 0.1
            self.heated_bed.current_temp += (self.heated_bed.target_temp - self.heated_bed.current_temp) * 0.05
            log_event(self.event_log, self.env, "Thermal_ECU", "TEMP_UPDATE",
                      {"hotend": self.print_head.current_temp, "bed": self.heated_bed.current_temp})