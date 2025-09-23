import time
import matplotlib.pyplot as plt
from visualization_3d import HighSpeedPrinterVisualizer3D, run_ultra_fast_visualization
def run_comparison_analysis(filename, max_moves=2000):
    """Compare simulation vs real machine performance"""
    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return
    
    print("="*60)
    print("SIMULATION vs REAL MACHINE COMPARISON")
    print("="*60)
    
    from gcode_analyzer import GCodeToInstructions, KinematicModel, parse_direction_string
    
    translator = GCodeToInstructions()
    kinematic_model = KinematicModel()
    instructions = translator.translate_gcode(gcode_lines)
    
    move_instructions = [inst for inst in instructions if inst.get('type', '').startswith('move_')]
    total_moves = min(len(move_instructions), max_moves)
    
    print(f"Analyzing {total_moves} moves...")
    print("\n1. SIMULATION TIMING ANALYSIS")
    print("-" * 40)
    
    # Simulation timing
    sim_start = time.time()
    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
    total_sim_time = 0.0
    total_distance = 0.0
    
    for instruction in move_instructions[:total_moves]:
        move_result = kinematic_model.execute_move(instruction)
        total_sim_time += move_result['move_time']
        total_distance += move_result['distance_3d']
        
        direction_movements = parse_direction_string(move_result['direction'])
        for axis, movement in direction_movements.items():
            current_pos[axis] += movement
    
    sim_elapsed = time.time() - sim_start
    
    print(f"Simulation calculated time: {total_sim_time:.2f} seconds")
    print(f"Actual processing time: {sim_elapsed:.2f} seconds")
    print(f"Total distance: {total_distance:.2f} mm")
    print(f"Simulation speed factor: {sim_elapsed/total_sim_time:.2f}x")
    
    print("\n2. REAL MACHINE ESTIMATION")
    print("-" * 40)
    
    # Real machine estimation (based on typical 3D printer specs)
    avg_print_speed = 50  # mm/s (typical FDM printer)
    avg_travel_speed = 150  # mm/s (typical rapid moves)
    
    estimated_print_time = total_distance / avg_print_speed  # Conservative estimate
    estimated_total_time = estimated_print_time * 1.2  # Include overhead
    
    print(f"Estimated real print time: {estimated_print_time:.2f} seconds")
    print(f"Estimated total time (with overhead): {estimated_total_time:.2f} seconds")
    print(f"Simulation to real time ratio: {total_sim_time/estimated_total_time:.2f}x")
    
    print("\n3. PERFORMANCE METRICS")
    print("-" * 40)
    print(f"Moves processed: {total_moves}")
    print(f"Simulation efficiency: {total_moves/sim_elapsed:.1f} moves/second")
    print(f"Data points generated: {total_moves}")
    
    # Ask if user wants to visualize
    visualize = input("\nWould you like to visualize the result? (y/n): ").strip().lower()
    if visualize == 'y':
        run_ultra_fast_visualization(filename, max_moves=total_moves)
        
def run_performance_benchmark(filename):
    """Run performance benchmark test"""
    print("\n" + "="*50)
    print("PERFORMANCE BENCHMARK")
    print("="*50)
    
    import time
    from gcode_analyzer import GCodeToInstructions, KinematicModel
    
    try:
        with open(filename, 'r') as file:
            gcode_lines = file.readlines()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return
    
    # Benchmark different components
    test_sizes = [100, 500, 1000, 2000]
    
    for size in test_sizes:
        print(f"\nTesting with {size} moves:")
        print("-" * 30)
        
        # Test G-code parsing
        start_time = time.time()
        translator = GCodeToInstructions()
        instructions = translator.translate_gcode(gcode_lines[:size*10])  # Approximate
        parse_time = time.time() - start_time
        print(f"G-code parsing: {parse_time:.3f}s ({size/parse_time:.1f} moves/s)")
        
        # Test kinematic calculations
        start_time = time.time()
        kinematic_model = KinematicModel()
        move_count = 0
        for instruction in instructions:
            if instruction.get('type', '').startswith('move_'):
                kinematic_model.execute_move(instruction)
                move_count += 1
                if move_count >= size:
                    break
        kin_time = time.time() - start_time
        print(f"Kinematic calculations: {kin_time:.3f}s ({size/kin_time:.1f} moves/s)")
        
        # Test visualization overhead
        if size <= 1000:  # Don't test large sizes for visualization
            visualizer = HighSpeedPrinterVisualizer3D(ultra_fast_mode=True)
            start_time = time.time()
            for i in range(size):
                visualizer.update_position_fast(i, i, i, 'PRINT')
            viz_time = time.time() - start_time
            print(f"Visualization overhead: {viz_time:.3f}s ({size/viz_time:.1f} moves/s)")
            plt.close(visualizer.fig)

