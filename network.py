import simpy

class NetworkBus:
    """CAN/UART bus using simpy.Store"""
    def __init__(self, env, latency=0.002):
        self.env = env
        self.latency = latency
        self.store = simpy.Store(env)

    def put(self, msg):
        return self.store.put((self.env.now + self.latency, msg))

    def get(self):
        return self.store.get()