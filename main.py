import numpy as np
from gcode_analyzer import analyze_gcode_file_with_visualization_realtime
import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job
from logger import Logger
import tkinter as tk
from admin_dashboard import PrinterGUI, run_simulation
import threading

def main():
    env = simpy.Environment()
    logger = Logger("simulation_log.jsonl")  # ✅ initialize logger

    printer = CyberPhysicalPrinter(env, logger)

    env.process(printer._thermal_control_loop())
    analyze_gcode_file_with_visualization_realtime()

    gcode_program = [
        "M104 S200",
        "M140 S60",
        "G1 X10 Y20 F1000",
        "G4 P1"
    ]

    env.process(run_print_job(env, printer, gcode_program))
    env.run(until=15)

    # ✅ Dump collected events into the JSONL log *before closing logger*
    for e in printer.event_log:
        logger.log(e["time"], e["component"], e["event_type"], e["details"])

    logger.close()
    print("Simulation finished. Events saved to simulation_log.jsonl")

    # ==== Start GUI ====
    root = tk.Tk()
    gui = PrinterGUI(root, env, printer)
    sim_thread = threading.Thread(target=run_simulation, args=(env, printer, gcode_program), daemon=True)
    sim_thread.start()
    root.mainloop()  # GUI loop (runs last)


if __name__ == "__main__":
    main()
