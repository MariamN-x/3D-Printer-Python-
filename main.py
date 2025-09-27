import numpy as np
from gcode_analyzer import analyze_gcode_file_with_visualization_realtime
from gcode_analyzer import select_gcode_file_gui
import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job
from logger import Logger
import tkinter as tk
from admin_dashboard import PrinterGUI, run_simulation
import multiprocessing
import gcode_analyzer
import time
import threading  # You were missing this import

def run_visualization_process():
    """Run visualization in a separate process"""
    try:
        print("Starting G-code visualization in separate process...")
        analyze_gcode_file_with_visualization_realtime()
        print("G-code visualization completed.")
    except Exception as e:
        print(f"Error in visualization process: {e}")

def run_simulation_thread(env, printer, gcode_program, logger):
    try:
        run_simulation(env, printer, gcode_program)
        logger.close()
        print("Simulation finished. Events saved to simulation_log.jsonl")
    except Exception as e:
        print(f"Simulation error: {e}")

def main():
    # First, get the G-code file BEFORE creating any Tkinter windows or processes
    print("Please select a G-code file for both visualization and simulation...")
    gcode_program = gcode_analyzer.gcode_for_simulation()
    
    if not gcode_program:
        print("No G-code program loaded. Operation canceled.")
        return  
        
    print(f"Loaded {len(gcode_program)} G-code instructions")
    
    # Ask user what they want to run
    print("\nChoose an option:")
    print("1. Run G-code visualization only")
    print("2. Run 3D printer simulation with GUI")
    print("3. Run both (visualization + simulation)")
    
    choice = input("Enter your choice (1/2/3): ").strip()
    
    if choice == "1":
        # Run visualization only
        print("Starting G-code visualization...")
        analyze_gcode_file_with_visualization_realtime()
        
    elif choice == "2":
        # Run simulation only
        run_simulation_only(gcode_program)
        
    elif choice == "3":
        # Run both using multiprocessing
        run_both_visualization_and_simulation(gcode_program)
        
    else:
        print("Invalid choice. Exiting.")

def run_simulation_only(gcode_program):
    """Run only the simulation with GUI"""
    env = simpy.Environment()
    logger = Logger("simulation_log.jsonl") 
    printer = CyberPhysicalPrinter(env, logger)
    
    # Create the main GUI
    root = tk.Tk()
    gui = PrinterGUI(root, env, printer)
    
    # Run simulation in a separate thread
    sim_thread = threading.Thread(
        target=run_simulation_thread, 
        args=(env, printer, gcode_program, logger), 
        daemon=True
    )
    sim_thread.start()
    
    # Start the GUI main loop
    root.mainloop()
    logger.close()
    print("Simulation GUI closed.")

def run_both_visualization_and_simulation(gcode_program):
    """Run both visualization and simulation"""
    # Start visualization in a separate process
    print("Starting visualization process...")
    visualization_process = multiprocessing.Process(
        target=run_visualization_process
    )
    visualization_process.start()
    
    # Give visualization a moment to start
    time.sleep(2)
    
    # Now start the simulation
    print("Starting simulation...")
    run_simulation_only(gcode_program)
    
    # Cleanup
    if visualization_process.is_alive():
        print("Terminating visualization process...")
        visualization_process.terminate()
        visualization_process.join()

if __name__ == "__main__":
    # Required for multiprocessing on Windows
    multiprocessing.freeze_support()
    main()
