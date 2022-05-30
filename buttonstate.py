SINGLE_KEY = "button_single"
DOUBLE_KEY = "button_double"
HOLD_KEY = "button_hold"

UPDATE_KEY = "update"

MAX_SINGLE = 5


class ButtonState:
    def __init__(self, r):
        self._r = r
        self._single = 0
        self._double = 0
        self._held = 0

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
        return self._single

    def set_single(self, value):
        self._single = value

    def get_double(self):
        return self._double

    def set_double(self, value):
        self._double = value

    def get_held(self):
        return self._held

    def set_held(self, value):
        self._held = value

    def flag_update(self):
        self._r.publish(UPDATE_KEY, "button")

    def refresh(self):
        self.set_single(int(self._r.get(SINGLE_KEY) or 0))
        self.set_double(int(self._r.get(DOUBLE_KEY) or 0))
        self.set_held(int(self._r.get(HOLD_KEY) or 0))
