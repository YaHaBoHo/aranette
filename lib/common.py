import utime

class Roller():

    def __init__(self, length, age) -> None:
        self.length = int(length)
        self.age  = int(age)
        self._list = list()

    def update(self, value):
        now = utime.time()
        self._list = [(t, v) for t, v in self._list[-self.length+1:] if t > now  - self.age] + [(now, value)]
        return sum(v for _, v in self._list) / len(self._list)
