from mbtastate import MBTAState
import requests
import threading

import time
import sys

from redislite import Redis
API_KEY = "9dd6a96deb434cca901b48f3a09b9479"
API_BASE = "https://api-v3.mbta.com"

headers = {
    "x-api-key": API_KEY,
    "accept": "text/event-stream"
}

# MBTA Stuff


def raise_error_event():
    print("Tried to apply an empty event - u suck bro")


class MBTAEvent:
    def set_type(self, type_str):
        if type_str == "reset":
            self._type = lambda s, e: s.apply_reset(e)
        elif type_str == "add":
            self._type = lambda s, e: s.apply_add(e)
        elif type_str == "update":
            self._type = lambda s, e: s.apply_update(e)
        elif type_str == "remove":
            self._type = lambda s, e: s.apply_remove(e)
        else:
            raise ValueError("Unknown event type: {}".format(type_str))

    def set_data(self, line):
        self._data = line

    def clear(self):
        self._type = lambda s, e: raise_error_event()
        self._data = ""

    def get_type(self):
        return self._type

    def get_data(self):
        return self._data

# MBTA Thread Stuff


def pred_stream(stop_id, direction_id, kill_event):
    state = MBTAState(
        Redis(host='127.0.0.1', port='6379',
              charset="utf-8", decode_responses=True))
    pred_stream_r = requests.get(API_BASE + "/predictions?filter[stop]={}&filter[direction_id]={}".format(
        stop_id, direction_id), headers=headers, stream=True)
    event_type_line = True
    current_event = MBTAEvent()
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
                current_event.get_type()(state, current_event)  # Apply event
                # state_update_event.set()
                current_event.clear()
                event_type_line = True


kill_event = threading.Event()

orange_north_thread = threading.Thread(
    target=pred_stream, args=('70013', '1', kill_event))
orange_south_thread = threading.Thread(
    target=pred_stream, args=('70012', '0', kill_event))
green_north_thread = threading.Thread(
    target=pred_stream, args=('70242', '1', kill_event))
green_south_thread = threading.Thread(
    target=pred_stream, args=('70241', '0', kill_event))

thread_list = [
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
    kill_event.set()
    for t in thread_list:
        print("Killing thread {}:".format(t.ident), end=" ")
        sys.stdout.flush()
        t.join()
        print("Done")
