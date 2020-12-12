SINGLE_KEY = "button_single"
DOUBLE_KEY = "button_double"
HOLD_KEY = "button_hold"

UPDATE_KEY = "update"

MAX_SINGLE = 3


class ButtonState:
    def __init__(self, r):
        self._r = r

    def single_click(self):
        s = self._r.incr(SINGLE_KEY)
        if s == MAX_SINGLE - 1:
            self._r.decrby(SINGLE_KEY, MAX_SINGLE)

    def double_click(self):
        s = int(self._r.get(DOUBLE_KEY) or 0)
        self._r.set(DOUBLE_KEY, int(not s))

    def hold(self):
        self._r.set(HOLD_KEY, 1)

    def release(self):
        s = int(self._r.get(HOLD_KEY) or 0)
        if s:
            self._r.set(HOLD_KEY, 0)
            return True
        return False

    def get_single(self):
        return int(self._r.get(SINGLE_KEY) or 0)

    def get_double(self):
        return int(self._r.get(DOUBLE_KEY) or 0)

    def get_held(self):
        return int(self._r.get(HOLD_KEY) or 0)

    def flag_update(self):
        self._r.publish(UPDATE_KEY, "button")
