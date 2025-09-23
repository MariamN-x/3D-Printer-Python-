import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Slider, Button
from mpl_toolkits.mplot3d import Axes3D
import time
from collections import deque
import matplotlib.animation as animation
import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job

class HighSpeedPrinterVisualizer3D:
    def __init__(self):
        self._setup_backend()
        
        # Set up the figure
        self.fig = plt.figure(figsize=(14, 10))
        self.ax = self.fig.add_axes([0.1, 0.25, 0.8, 0.7], projection='3d')
        
        # Data storage - PRE-ALLOCATED arrays for maximum speed
        self.max_points = 10000
        self.x_data = np.zeros(self.max_points)
        self.y_data = np.zeros(self.max_points) 
        self.z_data = np.zeros(self.max_points)
        self.movement_types = np.zeros(self.max_points, dtype=np.int8)
        self.current_index = 0
        
        # Track bounds for dynamic axis adjustment
        self.x_min, self.x_max = 0, 0
        self.y_min, self.y_max = 0, 0
        self.z_min, self.z_max = 0, 0
        self.x_center, self.y_center, self.z_center = 0, 0, 0
        
        # Visualization elements
        self.toolhead_point = self.ax.plot([0], [0], [0], 'ro', markersize=10)[0]
        self.path_line = self.ax.plot([0], [0], [0], 'b-', alpha=0.3, linewidth=1)[0]
        # self.display_indices = deque(maxlen=2000)  # Limited points for display
        
          # Text elements
        self.summary_text = None
        self.progress_text = None
        
        
        # Speed control and 
        self.simulation_speed = 1.0
        self.target_speed = 1.0
        self.is_paused = False
        self._closed = False
        
        # Batch processing - collect movements, render later
        self.pending_movements = []
        self.last_render_time = 0
        self.animation = None
        
        self.setup_plot()
        self.setup_controls()
        
        plt.ion()
        plt.show(block=False)
        plt.pause(0.1)
        
        print("HIGH-SPEED Visualizer Ready! Speeds up to 10,000x supported.")

    def _setup_backend(self):
        import matplotlib
        matplotlib.use('TkAgg')  # Force fastest backend

    def setup_plot(self):
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.set_zlabel('Z (mm)')
        self.ax.set_title('HIGH-SPEED 3D Printer Simulation')
        self.ax.grid(True)
        
        # Start with reasonable initial bounds centered at origin
        self.ax.set_xlim(-50, 50)
        self.ax.set_ylim(-50, 50)
        self.ax.set_zlim(0, 100)

    def setup_controls(self):
        # Ultra-wide speed slider
        slider_ax = self.fig.add_axes([0.15, 0.15, 0.7, 0.03])
        self.speed_slider = Slider(
            ax=slider_ax,
            label='Simulation Speed (log)',
            valmin=0,
            valmax=4.0,  # 1x to 10,000x
            valinit=0,
            valfmt='%0.0f x'
        )
        self.speed_slider.on_changed(self.update_speed)

        # Control buttons
        buttons_y = 0.05
        Button(self.fig.add_axes([0.1, buttons_y, 0.1, 0.04]), 'Play/Pause').on_clicked(self.toggle_pause)
        Button(self.fig.add_axes([0.25, buttons_y, 0.1, 0.04]), 'Center View').on_clicked(self.center_view)
        Button(self.fig.add_axes([0.4, buttons_y, 0.15, 0.04]), 'Fast Render').on_clicked(self.fast_render)
        Button(self.fig.add_axes([0.6, buttons_y, 0.15, 0.04]), 'Max Speed').on_clicked(self.max_speed)
        Button(self.fig.add_axes([0.8, buttons_y, 0.1, 0.04]), 'Skip All').on_clicked(self.skip_all)

        self.fig.canvas.mpl_connect('key_press_event', self.on_keypress)
        self.fig.canvas.mpl_connect('close_event', self.on_close)

    def update_speed(self, val):
        self.target_speed = 10 ** val  # 10^0=1x, 10^4=10,000x
        self.ax.set_title(f'HIGH-SPEED Simulation: {self.target_speed:.0f}x')
        self.fig.canvas.draw_idle()

    def toggle_pause(self, event=None):
        self.is_paused = not self.is_paused
        status = "PAUSED" if self.is_paused else "RUNNING"
        self.ax.set_title(f'HIGH-SPEED Simulation: {self.target_speed:.0f}x | {status}')
        self.fig.canvas.draw_idle()

    def center_view(self, event=None):
        """Center the view on the printed object"""
        if self.current_index > 0:
            self._calculate_center()
            range_x = self.x_max - self.x_min
            range_y = self.y_max - self.y_min
            range_z = self.z_max - self.z_min
            
            # Use the largest range to ensure object fits well in all dimensions
            max_range = max(range_x, range_y, range_z)
            margin = max_range * 0.2  # 20% margin
            
            if max_range == 0:  # Handle case where object is a single point
                max_range = 50
                margin = 10
                
            half_size = (max_range + 2 * margin) / 2
            
            self.ax.set_xlim(self.x_center - half_size, self.x_center + half_size)
            self.ax.set_ylim(self.y_center - half_size, self.y_center + half_size)
            self.ax.set_zlim(max(0, self.z_center - half_size), self.z_center + half_size)
        else:
            # Default centered view
            self.ax.set_xlim(-50, 50)
            self.ax.set_ylim(-50, 50)
            self.ax.set_zlim(0, 100)
        self.fig.canvas.draw_idle()

    def fast_render(self, event=None):
        """Render all collected data at once"""
        if self.current_index == 0:
            return
            
        print("Fast rendering all data...")
        # Show final result immediately
        self._render_frame(self.current_index)
        self.center_view()  # Center the view after fast render
        self.fig.canvas.draw_idle()

    def max_speed(self, event=None):
        """Set to maximum speed and process everything"""
        self.speed_slider.set_val(4.0)  # 10,000x
        self.fast_render()

    def skip_all(self, event=None):
        """Skip visualization entirely, just collect data"""
        print("Skipping visualization - data collection only")
        self.simulation_speed = 100000  # Effectively infinite

    def on_keypress(self, event):
        if event.key == ' ':
            self.toggle_pause()
        elif event.key == 'c':  # Changed from 'r' to 'c' for center
            self.center_view()
        elif event.key == 'f':
            self.fast_render()
        elif event.key == 'm':
            self.max_speed()
        elif event.key == 's':
            self.skip_all()

    def on_close(self, event):
        self._closed = True

    def add_movement_batch(self, movements):
        """Add multiple movements at once for maximum speed"""
        if self._closed or self.current_index >= self.max_points - len(movements):
            return False
            
        for movement in movements:
            if self.current_index < self.max_points:
                x, y, z, mov_type = movement
                self._update_bounds(x, y, z)
                self.x_data[self.current_index] = x
                self.y_data[self.current_index] = y
                self.z_data[self.current_index] = z
                self.movement_types[self.current_index] = 1 if mov_type == 'PRINT' else 2
                self.current_index += 1
                
        return True

    def update_position(self, x, y, z, movement_type):
        """Ultra-fast position update with centered axis adjustment"""
        if self._closed or self.current_index >= self.max_points:
            return False

        # Update bounds tracking
        self._update_bounds(x, y, z)

        # Store data immediately (FAST)
        self.x_data[self.current_index] = x
        self.y_data[self.current_index] = y  
        self.z_data[self.current_index] = z
        self.movement_types[self.current_index] = 1 if movement_type == 'PRINT' else 2
        self.current_index += 1

        # Visualization logic based on speed
        current_time = time.time()
        
        if self.target_speed >= 1000:  # Very high speed - minimal updates
            if current_time - self.last_render_time > 0.5:  # Update every 0.5s max
                self._render_frame(self.current_index)
                self.last_render_time = current_time
                plt.pause(0.001)
                
        elif self.target_speed >= 100:  # High speed - occasional updates
            if current_time - self.last_render_time > 0.1:
                self._render_frame(self.current_index)
                self.last_render_time = current_time
                plt.pause(0.001)
                
        elif self.target_speed >= 10:  # Medium speed - more frequent updates
            if current_time - self.last_render_time > 0.05:
                self._render_frame(self.current_index)
                self.last_render_time = current_time
                plt.pause(0.001)
                
        else:  # Normal speed - real-time updates
            self._render_frame(self.current_index)
            plt.pause(0.01 / self.target_speed)

        return True

    def _update_bounds(self, x, y, z):
        """Update the min/max bounds and calculate center"""
        if self.current_index == 0:
            # First point - initialize bounds
            self.x_min = self.x_max = x
            self.y_min = self.y_max = y
            self.z_min = self.z_max = z
            self._calculate_center()
        else:
            # Update bounds
            self.x_min = min(self.x_min, x)
            self.x_max = max(self.x_max, x)
            self.y_min = min(self.y_min, y)
            self.y_max = max(self.y_max, y)
            self.z_min = min(self.z_min, z)
            self.z_max = max(self.z_max, z)
            self._calculate_center()

    def _calculate_center(self):
        """Calculate the center point of the printed object"""
        self.x_center = (self.x_min + self.x_max) / 2
        self.y_center = (self.y_min + self.y_max) / 2
        self.z_center = (self.z_min + self.z_max) / 2

    def _render_frame(self, end_index):
        """Efficient rendering of current state with centered view"""
        if self._closed or end_index == 0:
            return

        # Show only recent points for performance
        start_idx = max(0, end_index - 1000)
        visible_indices = slice(start_idx, end_index)
        
        # Update path
        self.path_line.set_data(
            self.x_data[visible_indices], 
            self.y_data[visible_indices]
        )
        self.path_line.set_3d_properties(self.z_data[visible_indices])
        
        # Update toolhead
        if end_index > 0:
            self.toolhead_point.set_data(
                [self.x_data[end_index-1]], 
                [self.y_data[end_index-1]]
            )
            self.toolhead_point.set_3d_properties([self.z_data[end_index-1]])

        # Auto-center the view periodically
        if end_index % 200 == 0:  # Adjust every 200 points for smooth centering
            self._auto_center_view()

    def _auto_center_view(self):
        """Automatically center the view on the printed object"""
        if self.current_index == 0:
            return
            
        range_x = self.x_max - self.x_min
        range_y = self.y_max - self.y_min
        range_z = self.z_max - self.z_min
        
        # Use the largest range to ensure cubic view
        max_range = max(range_x, range_y, range_z)
        margin = max_range * 0.15  # 15% margin
        
        if max_range == 0:  # Handle case where object is a single point
            return  # Don't adjust view for single points
            
        half_size = (max_range + 2 * margin) / 2
        
        # Center the view around the object
        self.ax.set_xlim(self.x_center - half_size, self.x_center + half_size)
        self.ax.set_ylim(self.y_center - half_size, self.y_center + half_size)
        self.ax.set_zlim(max(0, self.z_center - half_size), self.z_center + half_size)

    def keep_open(self):
        """Keep the window open until user closes it"""
        if self._closed:
            return
            
        try:
            # Final updates
            self._render_frame(self.current_index)
            self.center_view()
            self.ax.set_title('Simulation COMPLETE - Close window to exit')
            
            # Add a text instruction
            if self.summary_text is None:
                self.fig.text(0.5, 0.01, "Close this window to continue...", 
                            ha='center', fontsize=12, 
                            bbox=dict(boxstyle="round,pad=0.5", facecolor="yellow"))
            
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
            
            # Switch to blocking mode
            plt.ioff()
            print("\n" + "="*60)
            print("Visualization complete! Close the window to continue.")
            print("="*60)
            plt.show(block=True)
            
        except Exception as e:
            print(f"Error keeping window open: {e}")
            # Fallback: wait for key press
            input("Press Enter to continue...")

    def on_close(self, event):
        """Handle window close event"""
        self._closed = True
        print("Visualization window closed by user.")
    
    def display_summary(self, summary_text):
        """Display final summary on the visualization"""
        try:
            # Clear any existing text
            if self.summary_text is not None:
                self.summary_text.remove()
            if self.progress_text is not None:
                self.progress_text.remove()
                
            # Display summary at the bottom of the figure
            self.summary_text = self.fig.text(
                0.02, 0.02, 
                summary_text, 
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.9),
                verticalalignment='bottom',
                horizontalalignment='left'
            )
            
            # Force immediate update
            self.fig.canvas.draw_idle()
            self.fig.canvas.flush_events()
            
            print("Summary displayed on visualization window")
            
        except Exception as e:
            print(f"Error displaying summary: {e}")
#================================================================================

#ADDITIONAL function for faster testing --> reserved for later progress

# Direct data injection
def simulate_instant_printer(visualizer, total_movements=100000):
    """Fastest possible simulation - direct data injection"""
    
    # Generate all data at once
    x_data = np.random.uniform(-40, 40, total_movements)
    y_data = np.random.uniform(-40, 40, total_movements)
    z_data = np.cumsum(np.random.uniform(-0.5, 1.5, total_movements))
    z_data = np.maximum(0, z_data)  # Ensure z >= 0
    movement_types = np.random.choice([1, 2], total_movements, p=[0.8, 0.2])
    
    # Inject data directly
    print("Injecting movement data...")
    visualizer.x_data[:total_movements] = x_data
    visualizer.y_data[:total_movements] = y_data
    visualizer.z_data[:total_movements] = z_data
    visualizer.movement_types[:total_movements] = movement_types
    visualizer.current_index = total_movements
    
    # Render final result
    visualizer.fast_render()
    print("Instant simulation complete!")

def run_simulation_only(gcode_program, simulation_time=100):
    """Run simulation without visualization (faster)"""
    env = simpy.Environment()
    printer = CyberPhysicalPrinter(env)
    
    env.process(printer._thermal_control_loop())
    env.process(run_print_job(env, printer, gcode_program))
    
    print(f"Running simulation for {simulation_time} seconds...")
    env.run(until=simulation_time)
    
    # Print results
    print("\n" + "="*50)
    print("SIMULATION COMPLETE")
    print("="*50)
    for e in printer.event_log:
        print(e)

def run_gcode_visualization_only(filename):
    """Run G-code visualization without SimPy simulation (fast visualization)"""
    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return
    
    print(f"Loading G-code file: {filename}")
    
    # Import the G-code analyzer components
    try:
        from gcode_analyzer import GCodeToInstructions, KinematicModel, parse_direction_string
    except ImportError:
        print("Error: G-code analyzer components not found.")
        return
    
    # Initialize visualizer
    visualizer = HighSpeedPrinterVisualizer3D()
    
    # Process the G-code
    translator = GCodeToInstructions()
    kinematic_model = KinematicModel()
    instructions = translator.translate_gcode(gcode_lines)

    print(f"Lines to process: {len(instructions)}")
    print("Starting G-code visualization...")
    print("Press Ctrl+C to stop early")

    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
    move_count = 0
    total_distance = 0.0
    total_time = 0.0

    try:
        for instruction in instructions:
            if instruction.get('type', '').startswith('move_'):
                move_result = kinematic_model.execute_move(instruction)
                
                # Parse movement from direction string
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
                
                total_distance += move_result['distance_3d']
                total_time += move_result['move_time']
                move_count += 1
                
                # Small delay for smooth visualization
                time.sleep(0.001)
                
                if move_count % 100 == 0:
                    print(f"Processed {move_count} moves...")
                    
            # Stop if we've processed a lot of moves (for testing)
            if move_count >= 100000:  # Adjust as needed
                print("Reached move limit for demonstration...")
                break
                
    except KeyboardInterrupt:
        print("\nVisualization interrupted by user.")
    except Exception as e:
        print(f"Error during visualization: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n" + "="*50)
        print("VISUALIZATION COMPLETE")
        print("="*50)
        print(f"Total moves visualized: {move_count}")
        print(f"Total distance: {total_distance:.2f} mm")
        print(f"Total time: {total_time:.2f} seconds")
        visualizer.keep_open()

def run_ultra_fast_simulation(gcode_program, speed_factor=100):
    """Run simulation with ULTRA-FAST visualization"""
    print(f"Starting ULTRA-FAST simulation at {speed_factor}x speed...")
    
    # Initialize high-speed visualizer
    vis = HighSpeedPrinterVisualizer3D()
    
    # Set initial speed
    if speed_factor > 1:
        log_speed = min(4.0, np.log10(speed_factor))  # Cap at 10,000x
        vis.speed_slider.set_val(log_speed)
    
    # Parse G-code and convert to movements
    movements = parse_gcode_to_movements(gcode_program)
    print(f"Processing {len(movements)} movements...")
    
    # Process movements using ultra-fast method
    start_time = time.time()
    
    # Use batch processing for maximum speed
    batch_size = max(100, min(1000, int(speed_factor)))
    
    for i in range(0, len(movements), batch_size):
        if vis._closed:
            break
            
        batch = movements[i:i + batch_size]
        vis.add_movement_batch(batch)
        
        # Progress update
        if i % 10000 == 0 and i > 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            print(f"Processed {i}/{len(movements)} movements ({rate:.0f} moves/sec)")
    
    # Final rendering
    vis.fast_render()
    
    elapsed = time.time() - start_time
    print(f"Simulation completed in {elapsed:.2f} seconds")
    print(f"Processing rate: {len(movements)/elapsed:.0f} movements/second")
    
    vis.keep_open()


def run_stress_test():
    """Run a stress test with massive amounts of data"""
    print("=== STRESS TEST ===")
    print("Testing with 100,000+ movements...")
    
    vis = HighSpeedPrinterVisualizer3D()
    
    # Generate massive movement data
    num_movements = 150000
    print(f"Generating {num_movements} movements...")
    
    # Use instant simulation for maximum speed
    simulate_instant_printer(vis, num_movements)
    
    print("Stress test complete!")
    vis.keep_open()

def parse_gcode_to_movements(gcode_lines):
    """Convert G-code lines to movement tuples (x, y, z, type)"""
    movements = []
    current_x, current_y, current_z = 0, 0, 0
    
    for line in gcode_lines:
        line = line.strip()
        if not line or line.startswith(';'):
            continue
            
        # Parse G1 movement commands
        if line.startswith('G1'):
            # Extract coordinates
            x = current_x
            y = current_y
            z = current_z
            
            if 'X' in line:
                x = extract_coordinate(line, 'X')
            if 'Y' in line:
                y = extract_coordinate(line, 'Y')
            if 'Z' in line:
                z = extract_coordinate(line, 'Z')
            
            # Determine movement type (simplified)
            movement_type = 'PRINT' if ('E' in line or 'F' in line) else 'RAPID'
            
            movements.append((x, y, z, movement_type))
            
            # Update current position
            current_x, current_y, current_z = x, y, z
            
        # Handle homing commands
        elif line.startswith('G28'):
            movements.append((0, 0, 0, 'RAPID'))
            current_x, current_y, current_z = 0, 0, 0
    
    return movements

def extract_coordinate(line, axis):
    """Extract coordinate value from G-code line"""
    try:
        axis_index = line.index(axis)
        value_str = ''
        for char in line[axis_index + 1:]:
            if char in '0123456789.-':
                value_str += char
            else:
                break
        return float(value_str) if value_str else 0
    except (ValueError, IndexError):
        return 0





# ==========================Testing section========================
# def main():
#  run_gcode_visualization_realtime()
# if __name__ == "__main__":
#     main()