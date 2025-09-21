
import json
from typing import Any, Dict

class Logger:
    """
    Simple JSON Lines logger for simulation events.
    Usage:
        from logger import Logger
        logger = Logger("simulation_log.jsonl")
        logger.log(env.now, "Motion_ECU", "move_start", {"X":10, "Y":20})
        logger.close()
    """
    def __init__(self, filename: str = "simulation_log.jsonl", auto_flush: bool = True):
        self.filename = filename
        self.file = open(filename, "w", encoding="utf-8")
        self.auto_flush = auto_flush

    def log(self, time: float, component: str, event_type: str, details: Dict[str, Any] = None):
        entry = {
            "time": float(time),
            "component": str(component),
            "event_type": str(event_type),
            "details": details or {}
        }
        # write a proper JSON line (newline character at the end)
        self.file.write(json.dumps(entry) + "\n")
        if self.auto_flush:
            self.file.flush()

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
