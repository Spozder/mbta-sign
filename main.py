from fliclib import ClickType
import fliclib
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import requests
import dateutil.parser
from dateutil.tz import tzutc
from json import loads
from enum import Enum
import threading
import logging
from datetime import datetime
import time
import sys
API_KEY = "9dd6a96deb434cca901b48f3a09b9479"
API_BASE = "https://api-v3.mbta.com"

# MBTA Stuff


def raise_error_event():
    print("Tried to apply an empty event - u suck bro")


def parse_line(l):
    return loads(l[l.index(" ")+1:])


class Prediction:
    def __init__(self, pred_id, route, direction_str, arrival_time_str):
        self._pred_id = pred_id
        self._route = route
        self._direction = int(direction_str)
        self._arrival_time = dateutil.parser.parse(arrival_time_str)

    def __lt__(self, other):
        return self._arrival_time < other._arrival_time

    def update_arrival_time(self, new_time):
        self._arrival_time = dateutil.parser.parse(new_time)

    def get_arrival_time(self):
        return self._arrival_time

    def get_route(self):
        return self._route

    def get_direction(self):
        return self._direction

    def remove(self):
        self._pred_id = "-REMOVED"

    def to_string(self, now=datetime.now(tzutc())):
        return "Prediction for {} line going {} (ID {}): {} ({} minutes from now)".format(
            self._route,
            ("North" if self._direction == 1 else "South"),
            self._pred_id.split(
                "-")[1] if self._pred_id.split("-")[1] != "ADDED" else self._pred_id.split("-")[2],
            self._arrival_time.strftime("%B %d, %Y - %l:%M:%S %p"),
            ((self._arrival_time - now).seconds // 60) % 60
        )

    def to_short_string(self, now=datetime.now(tzutc())):
        if self._route == "Orange":
            destination = "Oak Grove" if self._direction == 1 else "Forest Hills"
        else:
            destination = "Lechmere" if self._direction == 1 else "Heath St"
        return "{} {} min".format(
            destination,
            ((self._arrival_time - now).seconds // 60) % 60
        )


class MBTAState:
    def __init__(self):
        self._predictions_dict = {}
        self._lock = threading.Lock()

    def apply_reset(self, event):
        json_data = parse_line(event.get_data())
        for pred in json_data:
            self._predictions_dict[pred['id']] = Prediction(
                pred['id'],
                pred['relationships']['route']['data']['id'],
                pred['attributes']['direction_id'],
                pred['attributes']['arrival_time']
            )

    def apply_add(self, event):
        pred = parse_line(event.get_data())
        self._predictions_dict[pred['id']] = Prediction(
            pred['id'],
            pred['relationships']['route']['data']['id'],
            pred['attributes']['direction_id'],
            pred['attributes']['arrival_time']
        )

    def apply_update(self, event):
        pred = parse_line(event.get_data())
        self._predictions_dict[pred['id']].update_arrival_time(
            pred['attributes']['arrival_time'])

    def apply_remove(self, event):
        pred = parse_line(event.get_data())
        self._predictions_dict[pred['id']].remove()
        self._predictions_dict.pop(pred['id'], None)

    def get_lock(self):
        return self._lock

    def to_string(self, now=datetime.now(tzutc())):
        s = ""
        s += "Orange Line North\n"
        s += "-----------------\n"
        for pred in self.get_next_two_predictions("Orange", "1", now):
            s += pred.to_string(now) + "\n"
        s += "\n"

        s += "Orange Line South\n"
        s += "-----------------\n"
        for pred in self.get_next_two_predictions("Orange", "0", now):
            s += pred.to_string(now) + "\n"
        s += "\n"

        s += "Green Line North\n"
        s += "----------------\n"
        for pred in self.get_next_two_predictions("Green-E", "1", now):
            s += pred.to_string(now) + "\n"
        s += "\n"

        s += "Green Line South\n"
        s += "----------------\n"
        for pred in self.get_next_two_predictions("Green-E", "0", now):
            s += pred.to_string(now) + "\n"
        return s

    def get_next_two_predictions(self, route, direction_str, now=datetime.now(tzutc())):
        return sorted(
            filter(
                lambda pred: pred.get_arrival_time() > now and (pred.get_arrival_time() -
                                                                now).seconds > 60 and pred.get_route() == route and str(pred.get_direction()) == direction_str,
                self._predictions_dict.values()
            )
        )[:2]


class EventType(Enum):
    def RESET(state, event): return state.apply_reset(event)
    def ADD(state, event): return state.apply_add(event)
    def UPDATE(state, event): return state.apply_update(event)
    def REMOVE(state, event): return state.apply_remove(event)
    def ERROR(state, event): return raise_error_event()


class MBTAEvent:
    def set_type(self, type_str):
        if type_str == "reset":
            self._type = EventType.RESET
        elif type_str == "add":
            self._type = EventType.ADD
        elif type_str == "update":
            self._type = EventType.UPDATE
        elif type_str == "remove":
            self._type = EventType.REMOVE
        else:
            raise ValueError("Unknown event type: {}".format(type_str))

    def set_data(self, line):
        self._data = line

    def clear(self):
        self._type = EventType.ERROR
        self._data = ""

    def get_type(self):
        return self._type

    def get_data(self):
        return self._data

# MBTA Thread Stuff


def pred_stream(state, stop_id, direction_id, kill_event, state_update_event):
    pred_stream_r = requests.get(API_BASE + "/predictions?filter[stop]={}&filter[direction_id]={}".format(
        stop_id, direction_id), headers=headers, stream=True)
    event_type_line = True
    current_event = MBTAEvent()
    state_lock = state.get_lock()
    stream_iterator = pred_stream_r.iter_lines(decode_unicode=True)
    while not kill_event.is_set():
        try:
            line = next(stream_iterator)
        except:
            print("Connection broken, recreating")
            pred_stream_r = requests.get(API_BASE + "/predictions?filter[stop]={}&filter[direction_id]={}".format(
                stop_id, direction_id), headers=headers, stream=True)
            stream_iterator = pred_stream_r.iter_lines(decode_unicode=True)
            continue
        # filter out keep-alive new lines
        if line:
            if event_type_line:
                type_str = line.split(" ")[-1]
                # filter out keep-alive events
                if type_str == 'keep-alive':
                    continue
                # handle event-type line
                current_event.set_type(type_str)
                event_type_line = False
            else:
                # handle event-data line
                current_event.set_data(line)
                state_lock.acquire()
                current_event.get_type()(state, current_event)  # Apply event
                state_lock.release()
                state_update_event.set()
                current_event.clear()
                event_type_line = True


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
    def __init__(self):
        options = RGBMatrixOptions()

        # Setup sign options
        options.rows = 16
        options.cols = 96
        options.brightness = 50
        options.hardware_mapping = 'regular'
        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont(
            "/home/pi/mbta-sign/rpi-rgb-led-matrix/fonts/5x7.bdf")

    class Color(Enum):
        ORANGE = {
            "mbta_string": "Orange",
            "sign_color": graphics.Color(237, 139, 0)
        }
        GREEN = {
            "mbta_string": "Green-E",
            "sign_color": graphics.Color(0, 204, 0)
        }

    def set_text(self, line1, line2, color):
        print("Setting Text: {}, {}".format(line1, line2))
        self.canvas.Clear()
        graphics.DrawText(self.canvas, self.font, 1, 7, color, line1)
        graphics.DrawText(self.canvas, self.font, 1, 15, color, line2)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)


def update_sign(sign, mbta_state, button_state, kill_event, mbta_state_update_event, button_state_update_event):
    while not kill_event.is_set():
        if mbta_state_update_event.is_set() or button_state_update_event.is_set():
            print("Update Occuring")
            if mbta_state_update_event.is_set():
                print("MBTA State Update")
                mbta_state_update_event.clear()
            if button_state_update_event.is_set():
                print("Button State Update")
                button_state_update_event.clear()
            now = datetime.now(tzutc())
            color = Sign.Color.GREEN if button_state.get_single() else Sign.Color.ORANGE
            direction = "0" if button_state.get_double() else "1"
            line1 = ""
            line2 = ""
            if button_state.get_held():
                line1 = "I love"
                line2 = "Ranch ♡"
            else:
                predictions = mbta_state.get_next_two_predictions(
                    color.value["mbta_string"], direction, now)
                if len(predictions) > 0:
                    line1 = predictions[0].to_short_string(now)
                if len(predictions) > 1:
                    line2 = predictions[1].to_short_string(now)
            sign.set_text(line1, line2, color.value["sign_color"])


# Button Stuff


class ButtonState:
    def __init__(self):
        self.single = False
        self.double = False
        self.held = False

    def single_click(self):
        self.single = not self.single

    def double_click(self):
        self.double = not self.double

    def hold(self):
        self.held = True

    def release(self):
        if self.held:
            self.held = False
            return True
        return False

    def get_single(self):
        return self.single

    def get_double(self):
        return self.double

    def get_held(self):
        return self.held


def on_single_click(state, update_event):
    state.single_click()
    update_event.set()


def on_double_click(state, update_event):
    state.double_click()
    update_event.set()


def on_hold(state, update_event):
    state.hold()
    update_event.set()


def on_up(state, update_event):
    if state.release():
        update_event.set()


button_handling_dict = {
    ClickType.ButtonSingleClick: on_single_click,
    ClickType.ButtonDoubleClick: on_double_click,
    ClickType.ButtonHold: on_hold,
    ClickType.ButtonUp: on_up
}


def on_button_press_creator(state, update_event):
    def on_button_press(channel, click_type, was_queued, time_diff):
        print("Button Pressed!")
        if click_type in button_handling_dict:
            button_handling_dict[click_type](state, update_event)
        else:
            print("Unknown click type: {}".format(click_type))
    return on_button_press


def got_verified_button(bd_addr, state, update_event):
    cc = fliclib.ButtonConnectionChannel(bd_addr)

    # Add button event handlers
    cc.on_button_single_or_double_click_or_hold = on_button_press_creator(
        state, update_event)
    cc.on_button_up_or_down = on_button_press_creator(state, update_event)

    button_client.add_connection_channel(cc)


def got_flic_server_info_factory(state, update_event):
    def got_flic_server_info(info):
        for bd_addr in info["bd_addr_of_verified_buttons"]:
            got_verified_button(bd_addr, state, update_event)
    return got_flic_server_info


def handle_button_events(client):
    client.handle_events()


headers = {
    "x-api-key": API_KEY,
    "accept": "text/event-stream"
}

mbta_state = MBTAState()
kill_event = threading.Event()
kill_event.clear()
mbta_state_update_event = threading.Event()
mbta_state_update_event.clear()

button_state = ButtonState()
button_state_update_event = threading.Event()
button_state_update_event.clear()

button_client = fliclib.FlicClient("localhost")
button_client.get_info(got_flic_server_info_factory(
    button_state, button_state_update_event))

button_handler_thread = threading.Thread(
    target=handle_button_events, args=(button_client,))

sign = Sign()

#state_printer_thread = threading.Thread(target=print_state, args=(mbta_state, kill_event, mbta_state_update_event))
sign_updater_thread = threading.Thread(target=update_sign, args=(
    sign, mbta_state, button_state, kill_event, mbta_state_update_event, button_state_update_event))

orange_north_thread = threading.Thread(target=pred_stream, args=(
    mbta_state, '70013', '1', kill_event, mbta_state_update_event))
orange_south_thread = threading.Thread(target=pred_stream, args=(
    mbta_state, '70012', '0', kill_event, mbta_state_update_event))
green_north_thread = threading.Thread(target=pred_stream, args=(
    mbta_state, '70242', '1', kill_event, mbta_state_update_event))
green_south_thread = threading.Thread(target=pred_stream, args=(
    mbta_state, '70241', '0', kill_event, mbta_state_update_event))

thread_list = [
    button_handler_thread,
    sign_updater_thread,
    orange_north_thread,
    orange_south_thread,
    green_north_thread,
    green_south_thread
]
for t in thread_list:
    t.start()

try:
    while True:
        time.sleep(100)
except KeyboardInterrupt:
    print("Closing flic connection:", end=" ")
    button_client.close()
    print("Done")
    kill_event.set()
    for t in thread_list:
        print("Killing thread {}:".format(t.ident), end=" ")
        sys.stdout.flush()
        t.join()
        print("Done")
