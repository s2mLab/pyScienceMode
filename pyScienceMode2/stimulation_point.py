import sciencemode
class Point:
    point_stim = sciencemode.ffi.new("Smpt_ll_point*")
    def __init__(self, time: int, current: int):
        self.time = time
        self.current = current

    def validate(self):
        if not (0 <= self.time <= 4095):
            raise ValueError("Time must be between 0 and 100.")
        if not (-150 <= self.current <= 150):
            raise ValueError("Current must be between -20 and 20.")
