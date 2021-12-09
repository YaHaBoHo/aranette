import utime
import hashlib
import binascii


CFG_ENCODING = "utf-8"


def hash_sha256(text, rounds=1):
    # Initialize
    hash = text
    # Process
    for _ in range(rounds):
        hash = binascii.hexlify(
            hashlib.sha256(
                hash.encode(CFG_ENCODING)
            ).digest()
        ).decode(CFG_ENCODING)
    # Return
    return hash


def time_of_day(offset=0):
    tod = offset * 3600 + utime.time() % 86400
    th = tod // 3600
    tm = (tod % 3600) // 60
    return "{:02d}:{:02d}".format(th, tm)


class Roller():

    def __init__(self, length, age) -> None:
        self.length = int(length)
        self.age  = int(age)
        self._list = list()

    def update(self, value):
        now = utime.time()
        self._list = [(t, v) for t, v in self._list[-self.length+1:] if t > now  - self.age] + [(now, value)]
        return sum(v for _, v in self._list) / len(self._list)
