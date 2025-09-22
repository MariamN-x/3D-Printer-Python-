import simpy
import time
import threading
import tkinter as tk
from tkinter import ttk
from printer import CyberPhysicalPrinter
from job_runner import run_print_job


class PrinterGUI:
    def __init__(self, root, env, printer):
        self.root = root
        self.env = env
        self.printer = printer

        self.root.title("3D Printer Simulator")
        self.root.geometry("600x500")

        # --- Overview ---
        self.time_label = ttk.Label(root, text="Sim Time: 0.0s", font=("Arial", 12))
        self.time_label.pack(pady=5)

        # --- ECU States ---
        ecu_frame = ttk.LabelFrame(root, text="ECU States")
        ecu_frame.pack(fill="x", padx=10, pady=5)

        self.main_ecu_var = tk.StringVar()
        self.motion_ecu_var = tk.StringVar()
        self.thermal_ecu_var = tk.StringVar()

        ttk.Label(ecu_frame, text="Main ECU:").grid(row=0, column=0, sticky="w")
        ttk.Label(ecu_frame, textvariable=self.main_ecu_var).grid(row=0, column=1, sticky="w")

        ttk.Label(ecu_frame, text="Motion ECU:").grid(row=1, column=0, sticky="w")
        ttk.Label(ecu_frame, textvariable=self.motion_ecu_var).grid(row=1, column=1, sticky="w")

        ttk.Label(ecu_frame, text="Thermal ECU:").grid(row=2, column=0, sticky="w")
        ttk.Label(ecu_frame, textvariable=self.thermal_ecu_var).grid(row=2, column=1, sticky="w")

        # --- Temperatures with Progress Bars ---
        temp_frame = ttk.LabelFrame(root, text="Temperatures")
        temp_frame.pack(fill="x", padx=10, pady=5)

        # Hotend
        ttk.Label(temp_frame, text="Hotend:").grid(row=0, column=0, sticky="w")
        self.hotend_bar = ttk.Progressbar(temp_frame, length=300, maximum=250)  # max 250°C
        self.hotend_bar.grid(row=0, column=1, padx=5)
        self.hotend_label = ttk.Label(temp_frame, text="0 / 0 °C")
        self.hotend_label.grid(row=0, column=2, sticky="w")

        # Bed
        ttk.Label(temp_frame, text="Bed:").grid(row=1, column=0, sticky="w")
        self.bed_bar = ttk.Progressbar(temp_frame, length=300, maximum=120)  # max 120°C
        self.bed_bar.grid(row=1, column=1, padx=5)
        self.bed_label = ttk.Label(temp_frame, text="0 / 0 °C")
        self.bed_label.grid(row=1, column=2, sticky="w")

        # --- Filament ---
        filament_frame = ttk.LabelFrame(root, text="Filament")
        filament_frame.pack(fill="x", padx=10, pady=5)

        self.filament_var = tk.StringVar()
        ttk.Label(filament_frame, text="Remaining:").grid(row=0, column=0, sticky="w")
        ttk.Label(filament_frame, textvariable=self.filament_var).grid(row=0, column=1, sticky="w")

        # --- Events ---
        events_frame = ttk.LabelFrame(root, text="Recent Events")
        events_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.events_box = tk.Listbox(events_frame, height=10)
        self.events_box.pack(fill="both", expand=True)

        # start GUI update loop
        self.update_gui()

    def update_gui(self):
        # update overview
        self.time_label.config(text=f"Sim Time: {self.env.now:.2f}s")

        # update ECU states
        self.main_ecu_var.set(getattr(self.printer.main_ecu, "state", "N/A"))
        self.motion_ecu_var.set(getattr(self.printer.motion_ecu, "state", "N/A"))
        self.thermal_ecu_var.set(getattr(self.printer.thermal_ecu, "state", "N/A"))

        # update hotend
        hotend_temp = self.printer.print_head.current_temp
        hotend_target = self.printer.print_head.target_temp
        self.hotend_bar["value"] = hotend_temp
        self.hotend_label.config(text=f"{hotend_temp:.1f} / {hotend_target} °C")

        # update bed
        bed_temp = self.printer.heated_bed.current_temp
        bed_target = self.printer.heated_bed.target_temp
        self.bed_bar["value"] = bed_temp
        self.bed_label.config(text=f"{bed_temp:.1f} / {bed_target} °C")

        # update filament
        try:
            self.filament_var.set(f"{self.printer.filament.level:.1f} mm")
        except:
            self.filament_var.set("N/A")

        # update events
        self.events_box.delete(0, tk.END)
        for e in list(self.printer.event_log)[-8:]:
            if isinstance(e, dict):
                msg = f"[{e.get('time', '-'):.2f}] {e.get('component')} - {e.get('event_type')}"
            else:
                msg = str(e)
            self.events_box.insert(tk.END, msg)

        # schedule next update
        self.root.after(200, self.update_gui)


def run_simulation(env, printer, gcode_program):
    env.process(printer._thermal_control_loop())
    env.process(run_print_job(env, printer, gcode_program))

    # simulate in steps
    while env.now < 15:
        env.run(until=env.now + 0.2)
        time.sleep(0.2)


if __name__ == "__main__":
    env = simpy.Environment()
    printer = CyberPhysicalPrinter(env)

    gcode_program = [
        "M104 S200",
        "M140 S60",
        "G1 X10 Y20 F1000",
        "G4 P1"
    ]

    root = tk.Tk()
    gui = PrinterGUI(root, env, printer)

    # run sim in separate thread so GUI stays responsive
    sim_thread = threading.Thread(target=run_simulation, args=(env, printer, gcode_program), daemon=True)
    sim_thread.start()

    root.mainloop()
