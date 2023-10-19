import sciencemode


class Point:
    def __init__(self, time: float, current: float):
        self.time = time
        self.current = current
        self.check_parameters_point()

    def check_parameters_point(self):
        if not (0 <= self.time <= 4095):
            raise ValueError("Time must be between 0 and 4065.")
        if not (-150 <= self.current <= 150):
            raise ValueError("Current must be between -150 and 150.")
