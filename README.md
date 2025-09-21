# 🖨️ Cyber‑Physical 3D Printer Simulation (SimPy)

This project models a **3D printer as a cyber‑physical system** using SimPy

It separates the **physical world** (mechanics, actuators, materials) from the **cyber world** (controllers, computation, communication) and demonstrates how **commands, controllers, sensors, and physical states interact** inside a 3D printer.

---

## 📂 Project Structure
```plaintext
3d_printer_project/
│
├── main.py             # Entry point to run the simulation
├── printer.py          # CyberPhysicalPrinter class (ties actuators, ECUs, sensors, bus)
├── ecu.py              # ECU class (MainECU, MotionECU, ThermalECU)
├── actuator.py         # Actuator class (PrintHead, HeatedBed, Steppers)
├── sensor.py           # Sensor class + emulation process
├── network.py          # Network bus (CAN/UART) implemented with simpy.Store
├── job_runner.py       # Print job runner process
├── utils.py            # Shared utilities (event logging, state transitions)
└── README.md           # Project documentation
```

---

## 🚦 Simulation Components 

### 🌍 Physical 
- **Print Head (Hotend)**:  
  Actuator representing extruder. Has properties: `max_speed`, `current_temp`, `target_temp`.  

- **Heated Bed**:  
  Actuator representing bed heater. Has `current_temp`, `target_temp`.  

- **Steppers (X/Y/Z)**:  
  Actuators representing motion system. Properties: `position_x`, `position_y`, `position_z`.  

---

### 💻 Cyber Control Units
- **Main ECU**: parses G‑code, dispatches commands to other ECUs.  
- **Motion ECU**: calculates trajectories and manages steppers.  
- **Thermal ECU**: PID control loop for regulating hotend and bed temperatures.  

---

### 👀 Sensors
- **Thermistors**: simulate temp readings periodically; write values onto CAN bus.  
- **Endstops**: detect axis limits (to be added in later milestones).  
- **Filament Runout Sensor**: watches a `simpy.Container` for filament quantity; raises `Interrupt` when empty.  

---

### 🔌 Networks
- **CAN/Serial Bus**: implemented with `simpy.Store` (in future extended with `NetworkBus` class).  
  - Used to carry messages (`('sensor_update', value, time)`) between controllers.  
  - Includes a small transmission latency.  

---

### ⚡ Resources
- **Power Supply**: modeled as a `simpy.PreemptiveResource`.  
  - Required for all actions.  
  - Power failure events can pre‑empt running processes.  

---

## 🔁 Core Processes
- **_print_loop**:  
  Executes a sequence of G‑code commands (`G1`, `M104`, `M140`, `G4` etc.).  

- **_thermal_control_loop**:  
  Background physics process that adjusts `current_temp` toward `target_temp` (first‑order thermal system).  

- **_sensor_emulation_process**:  
  Simulates periodic readings (thermistors, filament sensors) and publishes them onto the CAN bus.  
