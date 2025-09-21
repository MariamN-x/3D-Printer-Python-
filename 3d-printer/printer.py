import simpy
import random
from ecu import ECU
from actuator import Actuator
from sensor import Sensor
from utils import log_event

class CyberPhysicalPrinter:
    def __init__(self, env):
        self.env = env
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

        self.event_log = []

        # sensors
        hotend_sensor = Sensor(env, "Hotend_Thermistor", 0.1, lambda: self.print_head.current_temp)
        bed_sensor = Sensor(env, "Bed_Thermistor", 0.1, lambda: self.heated_bed.current_temp)

        env.process(hotend_sensor.run(self.can_bus, self.event_log))
        env.process(bed_sensor.run(self.can_bus, self.event_log))
        env.process(self.sensor_filament())

    def sensor_filament(self):
        while True:
            yield self.env.timeout(1)
            if self.filament.level <= 0:
                self.main_ecu.set_state("ERROR", self.event_log)
                log_event(self.event_log, self.env, "Filament_Sensor", "FAULT",
                          {"msg": "Filament runout"})
                break

    def _print_loop(self, gcode_commands):
        for cmd in gcode_commands:
            yield self.env.process(self._execute_command(cmd))

    def _execute_command(self, gcode):
        with self.main_ecu.resource.request() as req:
            yield req
            self.main_ecu.set_state("PROCESSING", self.event_log)
            yield self.env.timeout(random.uniform(0.001, 0.005))

            if gcode.startswith("G1"):
                with self.motion_ecu.resource.request() as mreq:
                    yield mreq
                    self.motion_ecu.set_state("MOVING", self.event_log)
                    move_time = 0.5
                    yield self.env.timeout(move_time)
                    self.motion_ecu.set_state("IDLE", self.event_log)
                    log_event(self.event_log, self.env, "Motion_ECU", "cmd_sent",
                              {"command": gcode, "move_time": move_time})

            elif gcode.startswith("M104"):
                self.print_head.target_temp = 200
                log_event(self.event_log, self.env, "Thermal_ECU", "SET_TARGET",
                          {"hotend_target": self.print_head.target_temp})

            elif gcode.startswith("M140"):
                self.heated_bed.target_temp = 60
                log_event(self.event_log, self.env, "Thermal_ECU", "SET_TARGET",
                          {"bed_target": self.heated_bed.target_temp})

            elif gcode.startswith("G4"):
                dwell_time = 1.0
                yield self.env.timeout(dwell_time)
                log_event(self.event_log, self.env, "Main_ECU", "DWELL",
                          {"command": gcode, "duration": dwell_time})

            self.main_ecu.set_state("IDLE", self.event_log)

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