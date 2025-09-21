
# 🖨️ Cyber‑Physical 3D Printer Simulation (SimPy)

This project is a **simulation of a 3D printer** using [SimPy](https://simpy.readthedocs.io/).  

It separates the **physical world** (actuators, mechanics, material) from the **cyber world** (controllers, sensors, communication) and shows how a 3D printer’s brain and body work together.  

---

## 📂 Project Structure
```plaintext
3d_printer_project/
│
├── main.py             # Entry point to run the simulation
├── printer.py          # CyberPhysicalPrinter class (core logic + integration)
├── ecu.py              # ECU class (Main, Motion, Thermal ECUs)
├── actuator.py         # Actuator class (PrintHead, HeatedBed, Steppers)
├── sensor.py           # Sensor class + emulation loop
├── network.py          # Communication bus (CAN/UART, simpy.Store)
├── job_runner.py       # Print job runner
├── utils.py            # Logging and helpers
└── README.md           # Project documentation
```

---

## 🚦 Simulation Components
- **Physical Plant**: Print Head, Heated Bed, Steppers (X/Y/Z)  
- **Cyber Controllers (ECUs)**: Main ECU (parses G‑code), Motion ECU (handles motors), Thermal ECU (handles heaters)  
- **Sensors**: Thermistors, Endstops (later), Filament runout sensor  
- **Networks**: CAN/Serial bus with delays (`simpy.Store`)  
- **Resources**: Power supply modeled by `simpy.PreemptiveResource`  

---

## 🔁 Core Processes
- **_print_loop** → executes G‑codes in sequence  
- **_thermal_control_loop** → simulates heating physics dynamically  
- **_sensor_emulation_process** → thermistors provide periodic readings  

---

## 👨‍💻 Mina Atef — *Simulation Architect & Core Logic Lead* ✅  
**My Focus:** the core physical and data layers.  
- Designed the **class structure** (`Printer`, `ECU`, `Sensor`, `Actuator`, `NetworkBus`)  
- Implemented **core SimPy processes** (`_print_loop`, `_thermal_control_loop`, `_sensor_emulation_process`)  
- Modeled **communication** using `simpy.Store` for CAN bus, and implemented **fault injection** with `Interrupt` (filament runout sensor)  
- Built **state machine logic** for each ECU (`IDLE`, `PROCESSING`, `MOVING`, `HEATING`, `ERROR`)  

✅ Mine is **COMPLETE** 

---

## 👨‍💻 Georges & Mariam — *System Modelers & Data Generators* 🟡  
- Build a real **G‑code Parser** (now only 4 commands are hardcoded: `M104`, `M140`, `G1`, `G4`)  
- **Continue with other G‑codes** like `G28` (homing), `M109` (wait for hotend), `M190` (wait for bed), etc.  
- Add a proper **kinematic model** → move time = distance ÷ feedrate  
- Improve thermal model with more realistic curves  
- Define a clean **JSON event schema** for logs  

---

## 👩 Sama — *Application & Dashboard Lead* 🟡  
- Extend **main.py** with CLI arguments (`--gcode-file`, `--sim-speed`)  
- Build a **terminal UI dashboard** (with `curses` or `rich`) showing:  
  - Printer temps, positions, status  
  - Real‑time log  
  - Utilization bars  
- Add **simulation clock control** (faster/slower runs vs real time)  

---

## 👨‍🔬 Mina Adel — *Data Logger & Analysis Lead* 🟡  
- Save **event log** to structured `.jsonl` file instead of python list  
- Add **post‑simulation analysis** → ECU utilization, average command response times, failures, downtime  
- Use **matplotlib** to plot trends (temperature, utilization, message latency)  

---

## 🗂️ Current Example G‑code Job
```gcode
M104 S200      ; set hotend temp (non‑blocking)
M140 S60       ; set bed temp (non‑blocking)
G1 X10 Y20 F1000  ; move
G4 P1          ; wait 1 sec
```

> ⚠️ **Note**: Only a few sample G‑codes (`M104`, `M140`, `G1`, `G4`) are implemented now.  
The team must **continue adding the rest of the common G‑codes** in later .
