from prediction import Prediction, create_route_list_name

from json import loads
from datetime import datetime
from dateutil.tz import tzutc

UPDATE_KEY = "update"
DEBUG = False

MBTA_LOCK_KEY = "mbta"

PREDICTIONS_TO_WATCH = [
    ['70019', '1'],
    ['70018', '0'],
    ['70200', '1'],
    ['70199', '0'],
    ['70080', '1'],
    ['70079', '0']
]


def parse_line(l):
    return loads(l[l.index(" ")+1:])


class MBTAState:
    def __init__(self, r):
        self._r = r

    def apply_reset(self, event):
        json_data = parse_line(event.get_data())
        preds = []
        for pred in json_data:
            stop_id = str(pred['relationships']['stop']['data']['id'])
            direction_id = str(pred['attributes']['direction_id'])
            arrival_time = self.get_time(pred)
            if arrival_time is not None and [stop_id, direction_id] in PREDICTIONS_TO_WATCH:
                p = Prediction(
                    pred['id'],
                    pred['relationships']['route']['data']['id'],
                    pred['attributes']['direction_id'],
                    arrival_time
                )
                preds.append(p)
            else:
                if DEBUG:
                    print("Prediction not reset: {}, {}".format(stop_id, direction_id))

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
        stop_id = str(pred['relationships']['stop']['data']['id'])
        direction_id = str(pred['attributes']['direction_id'])
        arrival_time = self.get_time(pred)
        if arrival_time is not None and [stop_id, direction_id] in PREDICTIONS_TO_WATCH:
            p = Prediction(
                pred['id'],
                pred['relationships']['route']['data']['id'],
                pred['attributes']['direction_id'],
                arrival_time
            )
            p.add_to_redis(self._r)
            self.publish_update(p.get_route_list_name())
            if DEBUG:
                print("Added prediction:", p.to_short_string())
        else:
            if DEBUG:
                print("Prediction not added: {}, {}".format(stop_id, direction_id))

    def apply_update(self, event):
        pred = parse_line(event.get_data())
        p = Prediction.from_redis(self._r, pred['id'])
        if p:
            p.update_arrival_time(
                    pred['attributes']['arrival_time'] or
                    pred['attributes']['departure_time'])
            p.add_to_redis(self._r)
            self.publish_update(p.get_route_list_name())
            if DEBUG:
                print("Updated prediction: ", p.to_short_string())
        else:
            if DEBUG:
                print("No prediction to update")

    def apply_remove(self, event):
        pred = parse_line(event.get_data())
        p = Prediction.from_redis(self._r, pred['id'])
        if p:
            p.remove_from_redis(self._r)
            self.publish_update(p.get_route_list_name())
            if DEBUG:
                print("Removed prediction: ", p.to_short_string())
        else:
            if DEBUG:
                print("No prediction to remove")

    def publish_update(self, r_l_name):
        self._r.publish(UPDATE_KEY, r_l_name)

    def get_time(self, pred):
        return pred["attributes"]["arrival_time"] or pred["attributes"]["departure_time"]

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

    def acquire_lock(self):
        return self._r.lock(MBTA_LOCK_KEY)
