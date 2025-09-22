import simpy
import time
from printer import CyberPhysicalPrinter
from job_runner import run_print_job
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console

console = Console()

def render_dashboard(printer, env):
    layout = Layout()

    # --- Overview Panel ---
    overview_tbl = Table.grid(expand=True)
    overview_tbl.add_row(f"Sim Time: {env.now:.2f}s")
    overview_panel = Panel(overview_tbl, title="Overview")

    # --- Printer State Panel (Debug Mode) ---
    tbl = Table(title="Printer State (Debug Mode)")
    tbl.add_column("Field", style="cyan", no_wrap=True)
    tbl.add_column("Value", style="magenta")

    # ECU states
    tbl.add_row("Main ECU", str(getattr(printer.main_ecu, "state", "N/A")))
    tbl.add_row("Motion ECU", str(getattr(printer.motion_ecu, "state", "N/A")))
    tbl.add_row("Thermal ECU", str(getattr(printer.thermal_ecu, "state", "N/A")))

    # Hotend
    tbl.add_row("Hotend.current_temp", str(getattr(printer.print_head, "current_temp", "N/A")))
    tbl.add_row("Hotend.target_temp", str(getattr(printer.print_head, "target_temp", "N/A")))

    # Bed (debug all attributes)
    tbl.add_row("Bed.current_temp", str(getattr(printer.heated_bed, "current_temp", "N/A")))
    tbl.add_row("Bed.target_temp", str(getattr(printer.heated_bed, "target_temp", "N/A")))

    # Filament (show object + level explicitly)
    tbl.add_row("Filament.obj", str(printer.filament))
    try:
        tbl.add_row("Filament.level", str(printer.filament.level))
    except Exception as e:
        tbl.add_row("Filament.level", f"Error: {e}")

    printer_panel = Panel(tbl)

    # --- Recent Events Panel ---
    ev_tbl = Table(title="Recent Events", show_lines=True)
    ev_tbl.add_column("Time", style="yellow", width=6)
    ev_tbl.add_column("Component", style="cyan", width=18)
    ev_tbl.add_column("Type", style="green", width=14)
    ev_tbl.add_column("Details", style="white")

    if hasattr(printer, "event_log"):
        for e in list(printer.event_log)[-10:]:
            if isinstance(e, dict):
                time_str = f"{e.get('time', '-'):.2f}" if "time" in e else "-"
                component = str(e.get("component", "-"))
                evt_type = str(e.get("event_type", "-"))
                details = e.get("details", "-")
                if isinstance(details, dict):
                    details = ", ".join(
                        f"{k}={round(v,2) if isinstance(v,(int,float)) else v}"
                        for k, v in details.items()
                    )
                ev_tbl.add_row(time_str, component, evt_type, str(details))
            else:
                ev_tbl.add_row("-", "-", "-", str(e))

    events_panel = Panel(ev_tbl)

    # --- Layout assembly ---
    layout.split_column(
        Layout(overview_panel, size=3),
        Layout(printer_panel, size=12),
        Layout(events_panel, ratio=1),
    )
    return layout


# ---------------- Main Application ----------------
if __name__ == "__main__":
    env = simpy.Environment()
    printer = CyberPhysicalPrinter(env)

    # Start the thermal control loop
    env.process(printer._thermal_control_loop())

    # Example G-code program
    gcode_program = [
        "M104 S200",       # set hotend to 200 °C
        "M140 S60",        # set bed to 60 °C
        "G1 X10 Y20 F1000",# move head
        "G4 P1"            # pause for 1s
    ]
    env.process(run_print_job(env, printer, gcode_program))

    # Step-by-step simulation with live dashboard
    step = 0.2  # simulation step size
    try:
        with Live(render_dashboard(printer, env), refresh_per_second=10, screen=False) as live:
            while env.now < 15:  # run for 15s sim-time
                env.run(until=env.now + step)
                live.update(render_dashboard(printer, env))
                time.sleep(step)
    except KeyboardInterrupt:
        console.print("[red]Simulation interrupted by user[/red]")
