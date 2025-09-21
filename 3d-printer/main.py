import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job
from logger import Logger

if __name__ == "__main__":
    env = simpy.Environment()
    logger = Logger("simulation_log.jsonl")  # ✅ initialize logger

    printer = CyberPhysicalPrinter(env, logger)

    env.process(printer._thermal_control_loop())

    gcode_program = [
        "M104 S200",
        "M140 S60",
        "G1 X10 Y20 F1000",
        "G4 P1"
    ]

    env.process(run_print_job(env, printer, gcode_program))
    env.run(until=15)

    logger.close()
    print("Simulation finished. Events saved to simulation_log.jsonl")
