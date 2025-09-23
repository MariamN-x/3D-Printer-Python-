import math
import re
import sys
import os
from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D
from visualization_3d import HighSpeedPrinterVisualizer3D 
import time
import threading  
from queue import Queue
import tkinter as tk
from tkinter import filedialog

# ==================== PARSER ====================


class GCodeParser:
    def __init__(self):
        self.current_position = [0.0, 0.0, 0.0]  # X, Y, Z
        self.current_feedrate = 1000.0  # Default feedrate to prevent division by zero
        self.current_extrusion = 0.0
        self.absolute_positioning = True  # Default to absolute positioning

    def parse_gcode_line(self, line: str) -> Dict:
        """Parse a single G-code line and return command dictionary"""
        line = line.strip().upper()
        if not line or line.startswith(';'):
            return None

        # Remove comments
        if ';' in line:
            line = line.split(';')[0].strip()

        tokens = re.findall(r'([A-Z])([+-]?\d*\.?\d*)', line)
        command = {}

        for letter, value in tokens:
            if value:
                try:
                    command[letter] = float(value)
                except ValueError:
                    command[letter] = value

        # Extract G/M command
        g_match = re.search(r'([GM])(\d+)', line)
        if g_match:
            command_type, number = g_match.groups()
            command[command_type] = int(number)

        return command
    

# ==================== TRANSLATOR ====================

def parse_direction_string(direction_str):
    """Parse direction string like 'X_negative(6.88mm)+Y_positive(6.88mm)'"""
    import re
    movements = {}
    pattern = r'([XYZ])_(positive|negative)\(([\d.]+)mm\)'
    
    matches = re.findall(pattern, direction_str)
    for axis, direction, value in matches:
        numeric_value = float(value)
        if direction == 'negative':
            numeric_value = -numeric_value
        movements[axis] = numeric_value
    
    return movements

class GCodeToInstructions:
    def __init__(self):
        self.parser = GCodeParser()

    def translate_gcode(self, gcode_lines: List[str]) -> List[Dict]:
        """Translate G-code lines into machine instructions"""
        instructions = []

        for line_num, line in enumerate(gcode_lines, 1):
            try:
                command = self.parser.parse_gcode_line(line)
                if not command:
                    continue

                instruction = self._process_command(command, line_num)
                if instruction:
                    instructions.append(instruction)
            except Exception as e:
                print(f"Warning: Error parsing line {line_num}: {e}")
                continue

        return instructions

    def _calculate_euclidean_distance(self, start: List[float], end: List[float]) -> float:
        """Calculate 3D Euclidean distance between two points"""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dz = end[2] - start[2]
        return math.sqrt(dx**2 + dy**2 + dz**2)

    def _calculate_2d_distance(self, start: List[float], end: List[float]) -> float:
        """Calculate 2D distance (ignoring Z-axis)"""
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        return math.sqrt(dx**2 + dy**2)

    def _process_command(self, command: Dict, line_num: int) -> Optional[Dict]:
        """Process individual G/M commands with error handling"""
        try:
            if 'G' in command:
                g_code = command['G']

                if g_code in [0, 1]:  # Linear movement
                    return self._process_linear_move(command, g_code == 0, line_num)
                elif g_code in [2, 3]:  # Arc movement
                    return self._process_arc_move(command, g_code == 2, line_num)
                elif g_code == 28:  # Home
                    return self._process_home_command(command, line_num)
                elif g_code == 90:  # Absolute positioning
                    self.parser.absolute_positioning = True
                    return {'type': 'set_absolute_positioning', 'line': line_num}
                elif g_code == 91:  # Relative positioning
                    self.parser.absolute_positioning = False
                    return {'type': 'set_relative_positioning', 'line': line_num}

            elif 'M' in command:
                m_code = command['M']
                # Ignore thermal/fan commands
                if m_code in [104, 109, 106, 107]:
                    return {'type': 'ignored_command', 'code': f'M{m_code}', 'line': line_num}

            elif 'F' in command:
                self.parser.current_feedrate = command['F']
                return {
                    'type': 'set_feedrate',
                    'feedrate': command['F'],
                    'line': line_num
                }

            return {'type': 'unknown_command', 'command': command, 'line': line_num}

        except Exception as e:
            print(f"Error processing command on line {line_num}: {e}")
            return None

    def _process_linear_move(self, command: Dict, is_rapid: bool, line_num: int) -> Dict:
        """Process G0/G1 linear movement with proper distance calculation"""
        target_position = self.parser.current_position.copy()

        # Handle absolute vs relative positioning
        for axis in ['X', 'Y', 'Z', 'E']:
            if axis in command:
                if axis == 'E':
                    self.parser.current_extrusion = command[axis]
                else:
                    axis_index = {'X': 0, 'Y': 1, 'Z': 2}[axis]
                    if self.parser.absolute_positioning:
                        target_position[axis_index] = command[axis]
                    else:
                        target_position[axis_index] += command[axis]

        # Use current feedrate if not specified in this command
        current_feedrate = self.parser.current_feedrate
        if 'F' in command:
            current_feedrate = command['F']

        # Calculate distances
        distance_3d = self._calculate_euclidean_distance(
            self.parser.current_position,
            target_position
        )

        distance_2d = self._calculate_2d_distance(
            self.parser.current_position,
            target_position
        )

        # Calculate move time
        move_time = 0.0
        if distance_3d > 0 and current_feedrate > 0:
            move_time = (distance_3d / current_feedrate) * 60.0

        instruction = {
            'type': 'move_linear',
            'target_position': target_position,
            'current_position': self.parser.current_position.copy(),
            'feedrate': current_feedrate,
            'distance_3d': distance_3d,
            'distance_2d': distance_2d,
            'move_time': move_time,
            'is_rapid': is_rapid,
            'extrusion': self.parser.current_extrusion,
            'delta_x': target_position[0] - self.parser.current_position[0],
            'delta_y': target_position[1] - self.parser.current_position[1],
            'delta_z': target_position[2] - self.parser.current_position[2],
            'line': line_num
        }

        # Update feedrate for future commands
        if 'F' in command:
            self.parser.current_feedrate = command['F']

        self.parser.current_position = target_position.copy()
        return instruction

    def _process_arc_move(self, command: Dict, is_clockwise: bool, line_num: int) -> Dict:
        """Process G2/G3 arc movement"""
        target_position = self.parser.current_position.copy()

        for axis in ['X', 'Y', 'Z']:
            if axis in command:
                axis_index = {'X': 0, 'Y': 1, 'Z': 2}[axis]
                if self.parser.absolute_positioning:
                    target_position[axis_index] = command[axis]
                else:
                    target_position[axis_index] += command[axis]

        distance_3d = self._calculate_euclidean_distance(
            self.parser.current_position,
            target_position
        )

        current_feedrate = self.parser.current_feedrate
        if 'F' in command:
            current_feedrate = command['F']

        move_time = (distance_3d / current_feedrate) * \
            60.0 if distance_3d > 0 and current_feedrate > 0 else 0

        instruction = {
            'type': 'move_arc',
            'target_position': target_position,
            'current_position': self.parser.current_position.copy(),
            'feedrate': current_feedrate,
            'distance_3d': distance_3d,
            'move_time': move_time,
            'is_clockwise': is_clockwise,
            'delta_x': target_position[0] - self.parser.current_position[0],
            'delta_y': target_position[1] - self.parser.current_position[1],
            'delta_z': target_position[2] - self.parser.current_position[2],
            'line': line_num
        }

        if 'F' in command:
            self.parser.current_feedrate = command['F']

        self.parser.current_position = target_position.copy()
        return instruction

    def _process_home_command(self, command: Dict, line_num: int) -> Dict:
        """Process G28 - Home command"""
        home_position = [0.0, 0.0, 0.0]  # Assuming origin is home
        distance = self._calculate_euclidean_distance(
            self.parser.current_position, home_position)

        return {
            'type': 'move_linear',
            'target_position': home_position,
            'current_position': self.parser.current_position.copy(),
            'feedrate': 5000.0,  # High feedrate for homing
            'distance_3d': distance,
            'distance_2d': self._calculate_2d_distance(self.parser.current_position, home_position),
            'move_time': (distance / 5000.0) * 60.0 if distance > 0 else 0,
            'is_rapid': True,
            'delta_x': -self.parser.current_position[0],
            'delta_y': -self.parser.current_position[1],
            'delta_z': -self.parser.current_position[2],
            'line': line_num
        }

# ==================== KINEMATIC MODEL ====================


class KinematicModel:
    def __init__(self):
        self.current_position = [0.0, 0.0, 0.0]
        self.current_feedrate = 1000.0  # Default feedrate
        self.max_acceleration = 1000.0  # mm/s²
        self.max_jerk = 20.0  # mm/s

    def execute_move(self, instruction: Dict) -> Dict:
        """Execute a move instruction and return detailed movement information"""
        try:
            if instruction['type'] == 'move_linear':
                return self._execute_linear_move(instruction)
            elif instruction['type'] == 'move_arc':
                return self._execute_arc_move(instruction)
            return self._no_movement_output(instruction)
        except Exception as e:
            print(
                f"Error executing move from line {instruction.get('line', 'unknown')}: {e}")
            return self._no_movement_output(instruction)

    def _execute_linear_move(self, instruction: Dict) -> Dict:
        """Execute linear move with detailed distance information"""
        target = instruction['target_position']
        feedrate = instruction['feedrate']
        distance_3d = instruction['distance_3d']

        if distance_3d == 0:
            return self._no_movement_output(instruction)

        # Handle zero feedrate - use a default or previous feedrate
        if feedrate <= 0:
            if self.current_feedrate > 0:
                feedrate = self.current_feedrate  # Use previous feedrate
            else:
                feedrate = 1000.0  # Default feedrate (mm/min)

        # Calculate movement direction components
        dx = instruction['delta_x']
        dy = instruction['delta_y']
        dz = instruction['delta_z']

        # Determine primary direction with magnitudes
        directions = []
        if abs(dx) > 0:
            dir_type = "positive" if dx > 0 else "negative"
            directions.append(f"X_{dir_type}({abs(dx):.2f}mm)")
        if abs(dy) > 0:
            dir_type = "positive" if dy > 0 else "negative"
            directions.append(f"Y_{dir_type}({abs(dy):.2f}mm)")
        if abs(dz) > 0:
            dir_type = "positive" if dz > 0 else "negative"
            directions.append(f"Z_{dir_type}({abs(dz):.2f}mm)")

        direction_str = "+".join(directions) if directions else "no_movement"

        # Calculate move time with acceleration consideration
        move_time = self._calculate_move_time_with_acceleration(
            distance_3d, feedrate)

        # Update current position and feedrate
        self.current_position = target.copy()
        self.current_feedrate = feedrate

        return {
            'move_time': move_time,
            'direction': direction_str,
            'distance_3d': distance_3d,
            'distance_2d': instruction['distance_2d'],
            'feedrate': feedrate,
            'target_position': target.copy(),
            'current_position': instruction['current_position'].copy(),
            'movement_type': 'rapid' if instruction.get('is_rapid', False) else 'linear',
            'axis_movements': {'x': dx, 'y': dy, 'z': dz},
            'velocity_mm_s': feedrate / 60.0,
            'line': instruction.get('line', 0)
        }

    def _calculate_move_time_with_acceleration(self, distance: float, feedrate: float) -> float:
        """Calculate move time considering acceleration limits"""
        # Handle zero feedrate case
        if feedrate <= 0 or distance <= 0:
            return 0.0

        feedrate_mm_s = feedrate / 60.0

        # Time to accelerate to maximum speed
        acceleration_time = feedrate_mm_s / self.max_acceleration

        # Distance covered during acceleration
        acceleration_distance = 0.5 * self.max_acceleration * acceleration_time ** 2

        # Check if we can reach maximum speed
        if 2 * acceleration_distance > distance:
            # Triangular velocity profile
            total_time = 2 * math.sqrt(distance / self.max_acceleration)
        else:
            # Trapezoidal velocity profile
            coast_distance = distance - 2 * acceleration_distance
            coast_time = coast_distance / feedrate_mm_s
            total_time = 2 * acceleration_time + coast_time

        return total_time

    def _execute_arc_move(self, instruction: Dict) -> Dict:
        """Execute arc move and return detailed movement information"""
        linear_result = self._execute_linear_move(instruction)
        linear_result['movement_type'] = 'arc_clockwise' if instruction.get(
            'is_clockwise', False) else 'arc_counterclockwise'
        return linear_result

    def _no_movement_output(self, instruction: Dict) -> Dict:
        """Return output for no movement"""
        return {
            'move_time': 0.0,
            'direction': 'no_movement',
            'distance_3d': 0.0,
            'distance_2d': 0.0,
            'feedrate': self.current_feedrate,
            'movement_type': 'stationary',
            'velocity_mm_s': 0.0,
            'line': instruction.get('line', 0)
        }

# ==================== MAIN EXECUTION ====================

def generate_demo_gcode(num_movements=500):
    """Generate realistic demo G-code"""
    print(f"Generating demo with {num_movements} movements...")
    
    gcode = ["M104 S200", "M140 S60", "G28"]  # Startup commands
    
    x, y, z = 0, 0, 0
    
    for i in range(num_movements):
        # Generate realistic printer movements
        if i % 100 == 0:
            # Layer change
            z += 0.2
            gcode.append(f"G1 Z{z} F300")
        
        # Movement pattern
        angle = (i * 0.1) % (2 * np.pi)
        radius = 30 + 10 * np.sin(i * 0.05)
        
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        
        speed = 1500 if i % 20 == 0 else 800  # Faster for non-print moves
        
        gcode.append(f"G1 X{x:.2f} Y{y:.2f} Z{z:.2f} F{speed}")
        
        # Occasionally add temperature commands
        if i % 50 == 0:
            temp = 200 + (i % 20)
            gcode.append(f"M104 S{temp}")
    
    gcode.extend(["M104 S0", "M140 S0", "G28"])  # Shutdown commands
    return gcode

def analyze_gcode_file_with_visualization_realtime():
    """Real-time visualization that doesn't block the simulation"""
    # Call the GUI function to select file
    filename = select_gcode_file_gui()
    
    # Check if user selected a file or canceled
    if not filename:
        print("No file selected. Operation canceled.")
        return

    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return

    print(f"Analyzing G-code file: {filename}")
    
    # Initialize visualizer FIRST
    visualizer = HighSpeedPrinterVisualizer3D()
    
    # Process the G-code
    translator = GCodeToInstructions()
    kinematic_model = KinematicModel()

    instructions = translator.translate_gcode(gcode_lines)

    print(f"Lines to process: {len(instructions)}")
    print("\nStarting REAL-TIME 3D visualization...")

    total_time = 0.0
    total_distance = 0.0
    move_count = 0
    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}

    try:
        parser = GCodeParser()
        
        for instruction in instructions:
            if instruction['type'].startswith('move_'):
                move_result = kinematic_model.execute_move(instruction)
                
                # Parse direction movements
                try:
                    direction_movements = GCodeParser.parse_direction_string(move_result['direction'])
                except:
                    try:
                        direction_movements = parser.parse_direction_string(move_result['direction'])
                    except:
                        direction_movements = parse_direction_string(move_result['direction'])
                
                # Update current position
                for axis, movement in direction_movements.items():
                    current_pos[axis] += movement
                
                # Update visualization
                visualizer.update_position(
                    current_pos['X'], 
                    current_pos['Y'], 
                    current_pos['Z'],
                    move_result['movement_type']
                )
                
                total_time += move_result['move_time']
                total_distance += move_result['distance_3d']
                move_count += 1
                
                # Small delay for visualization
                if visualizer.target_speed < 100:  # Only delay for slower speeds
                    time.sleep(0.001)
                
                if move_count % 100 == 0:
                    print(f"Processed {move_count} moves...")
                    progress = (move_count / len(instructions)) * 100
                    if hasattr(visualizer, 'update_progress'):
                        visualizer.update_progress(progress, move_count, total_time, total_distance)
                    
            elif instruction['type'] == 'set_feedrate':
                time.sleep(0.0005)
                
            elif instruction['type'] == 'ignored_command':
                time.sleep(0.0001)

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
        if hasattr(visualizer, 'update_title'):
            visualizer.update_title("Simulation INTERRUPTED")
    except Exception as e:
        print(f"Error during simulation: {e}")
        if hasattr(visualizer, 'update_title'):
            visualizer.update_title(f"Simulation ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Calculate final statistics
        avg_speed = total_distance / total_time if total_time > 0 else 0
        avg_feedrate = avg_speed * 60 if total_time > 0 else 0
        
        print("-" * 100)
        print(f"SUMMARY:")
        print(f"Total moves analyzed: {move_count}")
        print(f"Total distance traveled: {total_distance:.2f} mm")
        print(f"Total movement time: {total_time:.2f} seconds")
        if total_time > 0:
            print(f"Average speed: {avg_speed:.1f} mm/s")
            print(f"Average feedrate: {avg_feedrate:.0f} mm/min")
        print("=" * 100)
        
        # Display summary on visualization dashboard
        summary_text = f"""SIMULATION COMPLETE

Summary:
• Total moves: {move_count}
• Total distance: {total_distance:.1f} mm
• Total time: {total_time:.1f} seconds
• Average speed: {avg_speed:.1f} mm/s
• Average feedrate: {avg_feedrate:.0f} mm/min

File: {os.path.basename(filename)}
        """
        if hasattr(visualizer, 'display_summary'):
            visualizer.display_summary(summary_text)
        
        # Keep visualization open with proper blocking
        print("Keeping visualization window open...")
        visualizer.keep_open()
        print("Visualization window closed. Program continuing...")
        
def analyze_gcode_file_visualization_only():
    """Fast visualization without simulation timing"""
    # Call the GUI function to select file
    filename = select_gcode_file_gui()
    
    # Check if user selected a file or canceled
    if not filename:
        print("No file selected. Operation canceled.")
        return

    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return

    print(f"Analyzing G-code file: {filename}")
    
    visualizer = HighSpeedPrinterVisualizer3D()
    translator = GCodeToInstructions()
    kinematic_model = KinematicModel()
    instructions = translator.translate_gcode(gcode_lines)

    print(f"Lines to process: {len(instructions)}")
    print("\nGenerating 3D visualization...")

    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
    move_count = 0

    try:
        for instruction in instructions:
            if instruction['type'].startswith('move_'):
                move_result = kinematic_model.execute_move(instruction)
                direction_movements = parse_direction_string(move_result['direction'])
                
                for axis, movement in direction_movements.items():
                    current_pos[axis] += movement
                
                visualizer.update_position(
                    current_pos['X'], current_pos['Y'], current_pos['Z'],
                    move_result['movement_type']
                )
                
                move_count += 1
                
                if move_count % 10 == 0:
                    time.sleep(0.001)
                
                if move_count % 500 == 0:
                    print(f"Processed {move_count} moves...")
                    
    except KeyboardInterrupt:
        print("\nVisualization interrupted.")

    print(f"Completed: {move_count} moves visualized")
    visualizer.keep_open()

def select_gcode_file_gui():
    """Open a file dialog to select G-code file"""
    root = tk.Tk()
    root.withdraw()  
    
    file_path = filedialog.askopenfilename(
        title="Select G-code File",
        filetypes=[
            ("G-code files", "*.gcode *.g *.gco"),
            ("All files", "*.*")
        ],
        initialdir=os.getcwd()  
    )
    
    root.destroy()
    
    return file_path



#==========================Testing section=======================
# def main():
#     # select_gcode_file_gui() #testing done
#     # analyze_gcode_file_with_visualization_realtime() #testing done
#     # analyze_gcode_file_visualization_only() #testing done

# if __name__ == "__main__":
#     main()