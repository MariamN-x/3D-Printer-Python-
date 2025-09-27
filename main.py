import simpy
from printer import CyberPhysicalPrinter
from job_runner import run_print_job

if __name__ == "__main__":
    env = simpy.Environment()
    printer = CyberPhysicalPrinter(env)

    env.process(printer._thermal_control_loop())


    gcode_program = [
    "M104 S200",          # Set hotend temp
    "M140 S60",           # Set bed temp
    "G1 X10 Y20 E5 F1000", # Move to X=10,Y=20 and extrude 5mm of filament
    "G1 X20 Y25 E3 F1000", # Move and extrude 3mm
    "G1 X20 Y25 E1000 F1000", # Move and extrude 3mm
    "G4 P1"               # Dwell for 1s
]


    env.process(run_print_job(env, printer, gcode_program))
    env.run(until=15)

    for e in printer.event_log:
        print(e)