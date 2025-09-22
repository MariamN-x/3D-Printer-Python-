import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job
import os
import sys
import time
from visualization_3d import PrinterVisualizer3D

def select_gcode_file():
    """Allow user to select a G-code file from the current directory"""
    gcode_files = [f for f in os.listdir() if f.lower().endswith(('.gcode', '.g', '.gco'))]
    
    if not gcode_files:
        print("No G-code files found in current directory.")
        print("Please place a .gcode file in the same directory as this script.")
        return None
    
    print("Available G-code files:")
    for i, file in enumerate(gcode_files, 1):
        print(f"{i}. {file}")
    
    while True:
        try:
            choice = input("\nSelect a file number (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(gcode_files):
                selected_file = gcode_files[choice_num - 1]
                print(f"Selected: {selected_file}")
                return selected_file
            else:
                print("Invalid selection. Please choose a valid number.")
                
        except ValueError:
            print("Please enter a valid number or 'q' to quit.")

def load_gcode_file(filename):
    """Load G-code from file"""
    try:
        with open(filename, 'r') as file:
            return [line.strip() for line in file.readlines() if line.strip()]
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

def run_simulation_with_visualization(gcode_program, simulation_time=100):
    """Run the simulation with 3D visualization"""
    env = simpy.Environment()
    printer = CyberPhysicalPrinter(env)
    
    # Initialize visualizer
    visualizer = PrinterVisualizer3D()
    
    # Add visualizer to printer for real-time updates
    printer.set_visualizer(visualizer)
    
    # Start thermal control loop
    env.process(printer._thermal_control_loop())
    
    # Run print job
    env.process(run_print_job(env, printer, gcode_program))
    
    print(f"Starting simulation for {simulation_time} seconds...")
    print("Press Ctrl+C to stop early")
    
    try:
        # Run simulation with periodic visualization updates
        start_time = env.now
        while env.now - start_time < simulation_time:
            env.run(until=env.now + 1)  # Run 1 second at a time
            
            # Update visualization with current printer state
            if hasattr(printer, 'current_position'):
                visualizer.update_position(
                    printer.current_position.get('X', 0),
                    printer.current_position.get('Y', 0), 
                    printer.current_position.get('Z', 0),
                    'PRINT'
                )
                
            # Print progress every 10 seconds
            if (env.now - start_time) % 10 == 0:
                print(f"Simulation time: {env.now - start_time:.1f}s")
                
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
    
    finally:
        # Print simulation results
        print("\n" + "="*50)
        print("SIMULATION COMPLETE")
        print("="*50)
        for e in printer.event_log[-20:]:  # Show last 20 events
            print(e)
        
        # Keep visualization open
        print("\nClose the visualization window to exit.")
        visualizer.keep_open()

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
    visualizer = PrinterVisualizer3D()
    
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
            if move_count >= 10000:  # Adjust as needed
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

def run_gcode_visualization_realtime(filename):
    """Run G-code visualization with realistic timing"""
    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return
    
    print(f"Loading G-code file: {filename}")
    
    try:
        from gcode_analyzer import GCodeToInstructions, KinematicModel, parse_direction_string
    except ImportError:
        print("Error: G-code analyzer components not found.")
        return
    
    visualizer = PrinterVisualizer3D()
    translator = GCodeToInstructions()
    kinematic_model = KinematicModel()
    instructions = translator.translate_gcode(gcode_lines)

    print(f"Lines to process: {len(instructions)}")
    print("Starting real-time G-code visualization...")
    print("Press Ctrl+C to stop early")

    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
    move_count = 0
    total_distance = 0.0
    total_time = 0.0

    try:
        for instruction in instructions:
            if instruction.get('type', '').startswith('move_'):
                move_result = kinematic_model.execute_move(instruction)
                
                direction_movements = parse_direction_string(move_result['direction'])
                
                for axis, movement in direction_movements.items():
                    current_pos[axis] += movement
                
                visualizer.update_position(
                    current_pos['X'], 
                    current_pos['Y'], 
                    current_pos['Z'],
                    move_result['movement_type']
                )
                
                total_distance += move_result['distance_3d']
                total_time += move_result['move_time']
                move_count += 1
                
                # Use actual move time for realistic simulation
                time.sleep(move_result['move_time'])
                
                if move_count % 50 == 0:
                    print(f"Processed {move_count} moves...")
                    
            if move_count >= 5000:  # Adjust as needed
                print("Reached move limit for demonstration...")
                break
                
    except KeyboardInterrupt:
        print("\nVisualization interrupted.")
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        print("\n" + "="*50)
        print("REAL-TIME VISUALIZATION COMPLETE")
        print("="*50)
        print(f"Total moves: {move_count}")
        print(f"Total distance: {total_distance:.2f} mm")
        print(f"Total time: {total_time:.2f} seconds")
        visualizer.keep_open()

def main():
    """Main function with enhanced menu interface"""
    print("="*70)
    print("3D PRINTER CYBER-PHYSICAL SYSTEM SIMULATION & VISUALIZATION")
    print("="*70)
    
    while True:
        print("\n" + "="*50)
        print("MAIN MENU")
        print("="*50)
        print("1. SimPy Simulation with 3D Visualization")
        print("2. SimPy Simulation Only (No Visualization)")
        print("3. G-code Visualization Only (Fast)")
        print("4. G-code Visualization with Real Timing")
        print("5. Demo Simulation (Built-in G-code)")
        print("6. Exit")
        print("="*50)
        
        choice = input("\nSelect an option (1-6): ").strip()
        
        if choice == '1':
            # SimPy simulation with visualization
            print("\n=== SimPy Simulation with 3D Visualization ===")
            filename = select_gcode_file()
            if filename:
                gcode_program = load_gcode_file(filename)
                if gcode_program:
                    sim_time = input("Enter simulation time in seconds (default: 100): ").strip()
                    sim_time = float(sim_time) if sim_time else 100
                    run_simulation_with_visualization(gcode_program, sim_time)
            
        elif choice == '2':
            # SimPy simulation only
            print("\n=== SimPy Simulation Only ===")
            filename = select_gcode_file()
            if filename:
                gcode_program = load_gcode_file(filename)
                if gcode_program:
                    sim_time = input("Enter simulation time in seconds (default: 100): ").strip()
                    sim_time = float(sim_time) if sim_time else 100
                    run_simulation_only(gcode_program, sim_time)
            
        elif choice == '3':
            # Fast G-code visualization
            print("\n=== Fast G-code Visualization ===")
            print("Shows complete print path quickly")
            filename = select_gcode_file()
            if filename:
                run_gcode_visualization_only(filename)
            
        elif choice == '4':
            # Real-time G-code visualization
            print("\n=== Real-time G-code Visualization ===")
            print("Shows movement with realistic timing")
            filename = select_gcode_file()
            if filename:
                run_gcode_visualization_realtime(filename)
            
        elif choice == '5':
            # Demo simulation
            print("\n=== Demo Simulation ===")
            demo_gcode = [
                "M104 S200",
                "M140 S60",
                "G28",
                "G1 X10 Y10 F1000",
                "G1 X20 Y20 F1500",
                "G1 Z5 F500",
                "G1 X0 Y0 Z0 F3000",
                "M104 S0",
                "M140 S0"
            ]
            print("Running demo simulation...")
            
            # Ask for demo type
            demo_choice = input("Demo with visualization? (y/n): ").strip().lower()
            if demo_choice == 'y':
                run_simulation_with_visualization(demo_gcode, 30)
            else:
                run_simulation_only(demo_gcode, 30)
            
        elif choice == '6':
            print("Exiting simulation.")
            break
            
        else:
            print("Invalid option. Please choose 1-6.")

if __name__ == "__main__":
    main()