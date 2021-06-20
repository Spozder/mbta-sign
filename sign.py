import sys
import time
from dateutil.tz import tzutc
from datetime import datetime
import logging
from enum import Enum
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from mbtastate import MBTAState
from buttonstate import ButtonState
from redis import Redis
UPDATE_KEY = "update"
BUTTON_KEY = "button"

DEBUG = False


def print_state(state, kill_event, state_update_event):
    state_lock = state.get_lock()
    last_updated_time = datetime.now(tzutc())
    while not kill_event.is_set():
        now = datetime.now(tzutc())
        if state_update_event.is_set() or (now - last_updated_time).seconds > 30:
            state_lock.acquire()
            clear_output(wait=True)
            print(state.to_string(now))
            state_lock.release()
            state_update_event.clear()
            last_updated_time = datetime.now(tzutc())
            time.sleep(0.1)


# Sign Stuff


class Sign:
    def __init__(self, r):
        options = RGBMatrixOptions()

        # Setup sign options
        options.rows = 16
        options.cols = 96
        options.brightness = 30
        options.hardware_mapping = 'regular'
        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont(
            "/home/pi/mbta-sign/rpi-rgb-led-matrix/fonts/5x7.bdf")

        self._r = r
        self._button_state = ButtonState(self._r)
        self._mbta_state = MBTAState(self._r)

        # Subscribe to channel
        self._pubsub = self._r.pubsub()
        self._pubsub.subscribe(UPDATE_KEY)

        self._line1 = ""
        self._line2 = ""

        self.set_text("Now booting up", "Pls hold", graphics.Color(102,51,153))

    class Color(Enum):
        ORANGE = {
            "mbta_string": "Orange",
            "sign_color": graphics.Color(237, 139, 0)
        }
        GREEN = {
            "mbta_string": "Green-E",
            "sign_color": graphics.Color(0, 204, 0)
        }
        RED = {
            "mbta_string": "Red",
            "sign_color": graphics.Color(255, 41, 28)
        }

    def set_text(self, line1, line2, color):
        if DEBUG:
            print("Setting Text: {}, {}".format(line1, line2))
        if line1 != self._line1 or line2 != self._line2:
            self.canvas.Clear()
            graphics.DrawText(self.canvas, self.font, 1, 7, color, line1)
            graphics.DrawText(self.canvas, self.font, 1, 15, color, line2)
            self.canvas = self.matrix.SwapOnVSync(self.canvas)
            self._line1 = line1
            self._line2 = line2

    def get_button_state_tuple(self):
        color = list(Sign.Color)[self._button_state.get_single()]
        direction = "0" if self._button_state.get_double() else "1"
        return color, direction

    def get_button_state_string(self):
        color, direction = self.get_button_state_tuple()
        # TODO: Use factored-out version
        return color.value["mbta_string"] + direction

    def handle_next_update(self):
        m = self._pubsub.get_message(timeout=0.1)
        if m:
            if DEBUG:
                print(m)
            if m['data'] == BUTTON_KEY or m['data'] == self.get_button_state_string() or self._button_state.get_held():
                if DEBUG:
                    print("Update Occuring")
                now = datetime.now(tzutc())
                color, direction = self.get_button_state_tuple()
                line1 = ""
                line2 = ""
                if self._button_state.get_held():
                    line1 = "I love"
                    line2 = "Ranch ♡"
                else:
                    with self._mbta_state.acquire_lock():
                        predictions = self._mbta_state.get_next_two_predictions(
                            color.value["mbta_string"], direction, now)
                    if len(predictions) > 0:
                        line1 = predictions[0].to_short_string(now)
                    if len(predictions) > 1:
                        line2 = predictions[1].to_short_string(now)
                self.set_text(line1, line2, color.value["sign_color"])

    def unsubscribe(self):
        self._pubsub.unsubscribe()


sign = Sign(Redis(host='127.0.0.1', port='6379',
                  charset="utf-8", decode_responses=True))

try:
    while True:
        sign.handle_next_update()
except KeyboardInterrupt:
    print("Sign Handler Interrupted")
    sign.unsubscribe()
