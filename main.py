import numpy as np
from gcode_analyzer import analyze_gcode_file_with_visualization_realtime
from gcode_analyzer import select_gcode_file_gui
import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job
from logger import Logger
import tkinter as tk
from admin_dashboard import PrinterGUI, run_simulation
import threading
import gcode_analyzer
import time

def run_simulation_thread(env, printer, gcode_program, logger):
    """Run the simulation in a separate thread using your run_simulation function"""
    try:
        run_simulation(env, printer, gcode_program)
        logger.close()
        print("Simulation finished. Events saved to simulation_log.jsonl")
    except Exception as e:
        print(f"Simulation error: {e}")

def main():
    env = simpy.Environment()
    logger = Logger("simulation_log.jsonl") 
    printer = CyberPhysicalPrinter(env, logger)
    gcode_program = gcode_analyzer.gcode_for_simulation()
    
    if not gcode_program:
        print("No G-code program loaded. Simulation cannot continue.")
        return  
        
    print(f"Loaded {len(gcode_program)} G-code instructions")
    
    root = tk.Tk()
    gui = PrinterGUI(root, env, printer)
    
    sim_thread = threading.Thread(
        target=run_simulation_thread, 
        args=(env, printer, gcode_program, logger), 
        daemon=True
    )
    sim_thread.start()
    root.mainloop()
    logger.close()

if __name__ == "__main__":
    main()