class Sensor:
    """General Sensor (Thermistor, Endstop, etc.)"""
    def __init__(self, env, name, interval, measure_fn):
        self.env = env
        self.name = name
        self.interval = interval
        self.measure_fn = measure_fn

    def run(self, bus, log):
        while True:
            yield self.env.timeout(self.interval)
            val = self.measure_fn()
            msg = ("sensor_reading", self.name, val, self.env.now)
            yield bus.put(msg)
            log.append({
                'time': self.env.now,
                'component': self.name,
                'event_type': 'SENSOR_READING',
                'details': {'value': val}
            })