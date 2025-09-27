import simpy

class ECU:
    """Cyber ECU (Main, Motion, Thermal)"""
    def __init__(self, env, name):
        self.env = env
        self.name = name
        self.resource = simpy.Resource(env, capacity=1)
        self.state = "IDLE"

    def set_state(self, new_state, log):
        if self.state != new_state:
            log.append({
                'time': self.env.now,
                'component': self.name,
                'event_type': 'STATE_CHANGE',
                'details': {'from': self.state, 'to': new_state}
            })
            self.state = new_state