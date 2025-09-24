
from logger import Logger
from analyze import run_all
from pathlib import Path
import random

OUT = Path(".")  # current folder
LOG = OUT / "simulation_log.jsonl"

def generate_mock_log(filename: str, total_time: float = 120.0):
    logger = Logger(filename)
    t = 0.0
    hotend = 25.0
    bed = 25.0
    cmd_id = 0
    while t < total_time:
        hotend += (150 - hotend) * 0.02 + random.normalvariate(0, 0.2)
        bed += (60 - bed) * 0.01 + random.normalvariate(0, 0.1)
        logger.log(t, "Thermal_ECU", "temp_update", {"current_temp": round(hotend,2)})
        logger.log(t, "Bed_ECU", "temp_update", {"current_temp": round(bed,2)})
        if int(t) % 3 == 0:
            duration = random.uniform(0.5, 2.0)
            logger.log(t, "Motion_ECU", "move_start", {"X": random.randint(0,200), "Y": random.randint(0,200)})
            logger.log(t + duration, "Motion_ECU", "move_end", {"X": random.randint(0,200), "Y": random.randint(0,200)})
        if int(t) % 2 == 0:
            cmd = f"G1 X{random.randint(0,200)} Y{random.randint(0,200)} F1500"
            logger.log(t, "Main_ECU", "cmd_received", {"cmd": cmd, "id": cmd_id})
            logger.log(t + 0.01, "Main_ECU", "cmd_start", {"id": cmd_id})
            logger.log(t + 0.5, "Main_ECU", "cmd_end", {"id": cmd_id})
            cmd_id += 1
        if random.random() < 0.01:
            logger.log(t, "Sensor", "filament_runout", {"remaining": 0})
            logger.log(t + 1.0, "Main_ECU", "downtime_start", {"reason": "filament"})
            logger.log(t + 3.0, "Main_ECU", "downtime_end", {"reason": "filament"})
        t += 1.0
    logger.close()

if __name__ == "__main__":
    generate_mock_log(str(LOG), total_time=120.0)
    run_all(str(LOG))
