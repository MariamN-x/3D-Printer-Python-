import math
import re
import sys
from typing import List, Dict, Optional

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


def analyze_gcode_file(filename: str):
    """Load G-code file and perform kinematic analysis"""
    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    print(f"Analyzing G-code file: {filename}")
    print(f"Lines to process: {len(gcode_lines)}")

    # Process the G-code
    translator = GCodeToInstructions()
    kinematic_model = KinematicModel()

    instructions = translator.translate_gcode(gcode_lines)

    # Print analysis header
    print("\n" + "=" * 100)
    print("G-CODE KINEMATIC ANALYSIS")
    print("=" * 100)
    print(f"{'Line':<6} {'Type':<12} {'Direction':<35} {'Distance':<10} {'Time':<8} {'Speed':<10}")
    print("-" * 100)

    total_time = 0.0
    total_distance = 0.0
    move_count = 0

    for instruction in instructions:
        if instruction['type'].startswith('move_'):
            move_result = kinematic_model.execute_move(instruction)

            print(f"{instruction.get('line', 'N/A'):<6} {move_result['movement_type']:<12} {move_result['direction']:<35} "
                  f"{move_result['distance_3d']:>9.2f}mm {move_result['move_time']:>7.2f}s "
                  f"{move_result['velocity_mm_s']:>9.1f}mm/s")

            total_time += move_result['move_time']
            total_distance += move_result['distance_3d']
            move_count += 1

        elif instruction['type'] == 'set_feedrate':
            print(f"{instruction.get('line', 'N/A'):<6} {'FEEDRATE':<12} {f'Set to {instruction['feedrate']} mm/min':<35} {
                  '-':>10} {'-':>8} {'-':>10}")

        elif instruction['type'] == 'ignored_command':
            print(
                f"{instruction.get('line', 'N/A'):<6} {'IGNORED':<12} {instruction['code']:<35} {'-':>10} {'-':>8} {'-':>10}")

    # Print summary
    print("-" * 100)
    print(f"SUMMARY:")
    print(f"Total moves analyzed: {move_count}")
    print(f"Total distance traveled: {total_distance:.2f} mm")
    print(f"Total movement time: {total_time:.2f} seconds")
    if total_time > 0:
        print(f"Average speed: {total_distance/total_time:.1f} mm/s")
        print(f"Average feedrate: {(total_distance/total_time)*60:.0f} mm/min")
    print("=" * 100)


def main():
    """Main function to handle command line input"""
    if len(sys.argv) != 2:
        print("Usage: python gcode_analyzer.py <gcode_file>")
        print("Example: python gcode_analyzer.py sample.gcode")
        sys.exit(1)

    filename = sys.argv[1]
    analyze_gcode_file(filename)


if __name__ == "__main__":
    main()
