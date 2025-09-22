import simpy

class Actuator:
    """Physical Actuator (Print Head, Bed, Steppers)"""
    def __init__(self, env, name, capacity=1):
        self.env = env
        self.name = name
        self.resource = simpy.Resource(env, capacity=capacity)
        self.current_temp = 25
        self.target_temp = 25
        self.position_x = 0
        self.position_y = 0
        self.position_z = 0