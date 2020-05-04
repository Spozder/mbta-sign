from redislite import Redis

BUTTON_KEY = "button"
SINGLE_OFFSET = 0
DOUBLE_OFFSET = 1
HOLD_OFFSET = 2

UPDATE_KEY = "update"


class ButtonState:
    def __init__(self, r=Redis('/tmp/mbta.db', charset="utf-8", decode_responses=True)):
        self._r = r

    def single_click(self):
        s = self._r.getbit(BUTTON_KEY, SINGLE_OFFSET)
        self._r.setbit(BUTTON_KEY, SINGLE_OFFSET, not s)

    def double_click(self):
        s = self._r.getbit(BUTTON_KEY, DOUBLE_OFFSET)
        self._r.setbit(BUTTON_KEY, SINGLE_OFFSET, not s)

    def hold(self):
        self._r.setbit(BUTTON_KEY, SINGLE_OFFSET, True)

    def release(self):
        s = self._r.getbit(BUTTON_KEY, HOLD_OFFSET)
        if s:
            self._r.setbit(BUTTON_KEY, HOLD_OFFSET, False)
            return True
        return False

    def get_single(self):
        return self._r.getbit(BUTTON_KEY, SINGLE_OFFSET)

    def get_double(self):
        return self._r.getbit(BUTTON_KEY, DOUBLE_OFFSET)

    def get_held(self):
        return self._r.getbit(BUTTON_KEY, HOLD_OFFSET)

    def flag_update(self):
        self._r.publish(UPDATE_KEY, BUTTON_KEY)
