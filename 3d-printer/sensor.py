class Sensor:
    """General Sensor (Thermistor, Endstop, etc.)"""
    def __init__(self, env, name, interval, measure_fn, logger):
        self.env = env
        self.name = name
        self.interval = interval
        self.measure_fn = measure_fn
        self.logger = logger

    def run(self, bus):
        while True:
            yield self.env.timeout(self.interval)
            val = self.measure_fn()
            msg = ("sensor_reading", self.name, val, self.env.now)
            yield bus.put(msg)
            self.logger.log(
                self.env.now,
                self.name,
                "SENSOR_READING",
                {"value": val}
            )
