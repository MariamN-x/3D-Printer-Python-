import simpy

class ECU:
    """Cyber ECU (Main, Motion, Thermal)"""
    def __init__(self, env, name, logger):
        self.env = env
        self.name = name
        self.logger = logger
        self.resource = simpy.Resource(env, capacity=1)
        self.state = "IDLE"

    def set_state(self, new_state):
        if self.state != new_state:
            self.logger.log(
                self.env.now,
                self.name,
                "STATE_CHANGE",
                {"from": self.state, "to": new_state}
            )
            self.state = new_state
