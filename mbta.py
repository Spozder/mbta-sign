from prediction import Prediction, create_route_list_name

import requests
import dateutil.parser
from dateutil.tz import tzutc
from json import loads

import threading

from datetime import datetime
import time
import sys

from redislite import Redis
UPDATE_KEY = "update"

DEBUG = True

API_KEY = "9dd6a96deb434cca901b48f3a09b9479"
API_BASE = "https://api-v3.mbta.com"

headers = {
    "x-api-key": API_KEY,
    "accept": "text/event-stream"
}

# MBTA Stuff


def raise_error_event():
    print("Tried to apply an empty event - u suck bro")


def parse_line(l):
    return loads(l[l.index(" ")+1:])


class MBTAState:
    def __init__(self, r=Redis('/tmp/mbta.db', charset="utf-8", decode_responses=True)):
        self._r = r

    def apply_reset(self, event):
        json_data = parse_line(event.get_data())
        preds = []
        for pred in json_data:
            p = Prediction(
                pred['id'],
                pred['relationships']['route']['data']['id'],
                pred['attributes']['direction_id'],
                pred['attributes']['arrival_time']
            )
            preds.append(p)

        if len(preds) > 0:
            r_l_name = preds[0].get_route_list_name()
            for id_to_delete in self._r.sscan_iter(r_l_name):
                Prediction.from_redis(
                    self._r, id_to_delete).remove_from_redis(self._r)
            for p in preds:
                p.add_to_redis(self._r)
                if DEBUG:
                    print("Added prediction:", p.to_short_string())
            self.publish_update(r_l_name)

    def apply_add(self, event):
        pred = parse_line(event.get_data())
        p = Prediction(
            pred['id'],
            pred['relationships']['route']['data']['id'],
            pred['attributes']['direction_id'],
            pred['attributes']['arrival_time']
        )
        p.add_to_redis(self._r)
        self.publish_update(p.get_route_list_name())
        if DEBUG:
            print("Added prediction:", p.to_short_string())

    def apply_update(self, event):
        pred = parse_line(event.get_data())
        p = Prediction.from_redis(self._r, pred['id'])
        p.update_arrival_time(pred['attributes']['arrival_time'])
        p.add_to_redis(self._r)
        self.publish_update(p.get_route_list_name())
        if DEBUG:
            print("Updated prediction: ", p.to_short_string())

    def apply_remove(self, event):
        pred = parse_line(event.get_data())
        p = Prediction.from_redis(self._r, pred['id'])
        p.remove_from_redis(self._r)
        self.publish_update(p.get_route_list_name())
        if DEBUG:
            print("Removed prediction: ", p.to_short_string())

    def publish_update(self, r_l_name):
        self._r.publish(UPDATE_KEY, r_l_name)

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
        preds = map(lambda id: Prediction.from_redis(self._r, id),
                    self._r.smembers(create_route_list_name(route, direction_str)))
        return sorted(
            filter(
                lambda pred: pred.get_arrival_time() > now and (
                    pred.get_arrival_time() - now).seconds > 60,
                preds
            )
        )[:2]


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
    state = MBTAState()
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
