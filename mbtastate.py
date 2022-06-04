from prediction import Prediction, create_route_list_name

from datetime import datetime
from dateutil.tz import tzutc

UPDATE_KEY = "update"
DEBUG = False

MBTA_LOCK_KEY = "mbta"

PREDICTIONS_TO_WATCH = [
    ["70019", "1"],
    ["70018", "0"],
    ["70158", "1"],
    ["70159", "0"],
    ["70080", "1"],
    ["70079", "0"],
    ["70042", "1"],
    ["70041", "0"],
    ["74611", "0"],
]

LINES_TO_WATCH = ["Red", "Orange", "Green", "Blue"]

SHORTENED_HEADSIGNS = {
    "Government Center": "Gov Center",
    "Cleveland Circle": "Cleveland Cir",
    "Boston College": "Boston Col",
}


def shorten_headsign(headsign):
    if headsign in SHORTENED_HEADSIGNS:
        return SHORTENED_HEADSIGNS[headsign]
    return headsign[:13]


class MBTAState:
    def __init__(self, r):
        self._r = r

    def apply_reset(self, event):
        json_data = event.get_data()
        preds = []
        trip_headsigns = {}
        for resource in json_data:
            if resource["type"] == "trip":
                trip = resource
                trip_id = trip["id"]
                headsign = shorten_headsign(trip["attributes"]["headsign"])
                trip_headsigns[trip_id] = headsign

            elif resource["type"] == "prediction":
                pred = resource
                stop_id = str(pred["relationships"]["stop"]["data"]["id"])
                direction_id = str(pred["attributes"]["direction_id"])
                arrival_time = self.get_time(pred)
                if (
                    arrival_time is not None
                    and [stop_id, direction_id] in PREDICTIONS_TO_WATCH
                ):
                    p = Prediction(
                        pred["id"],
                        str(pred["relationships"]["route"]["data"]["id"]),
                        pred["attributes"]["direction_id"],
                        str(pred["relationships"]["trip"]["data"]["id"]),
                        arrival_time,
                        None,
                    )
                    preds.append(p)
                else:
                    if DEBUG:
                        print(
                            "Prediction not reset: {}, {}".format(stop_id, direction_id)
                        )

        if len(preds) > 0:
            r_l_name = preds[0].get_route_list_name()
            for id_to_delete in self._r.sscan_iter(r_l_name):
                Prediction.from_redis(self._r, id_to_delete).remove_from_redis(self._r)
            for p in preds:
                p.set_headsign(trip_headsigns[p.get_trip_id()])
                p.add_to_redis(self._r)
                if DEBUG:
                    print("Added prediction:", p.to_short_string())
            self.publish_update(r_l_name)

    def apply_add(self, event):
        resource = event.get_data()
        if resource["type"] == "trip":
            trip = resource
            Prediction.set_headsign_in_redis(
                self._r, trip["id"], shorten_headsign(trip["attributes"]["headsign"])
            )
        elif resource["type"] == "prediction":
            pred = resource
            stop_id = str(pred["relationships"]["stop"]["data"]["id"])
            direction_id = str(pred["attributes"]["direction_id"])
            arrival_time = self.get_time(pred)
            if (
                arrival_time is not None
                and [stop_id, direction_id] in PREDICTIONS_TO_WATCH
            ):
                p = Prediction(
                    pred["id"],
                    str(pred["relationships"]["route"]["data"]["id"]),
                    pred["attributes"]["direction_id"],
                    str(pred["relationships"]["trip"]["data"]["id"]),
                    arrival_time,
                    None,
                )
                p.add_to_redis(self._r)
                self.publish_update(p.get_route_list_name())
                if DEBUG:
                    print("Added prediction:", p.to_short_string())
            else:
                if DEBUG:
                    print("Prediction not added: {}, {}".format(stop_id, direction_id))

    def apply_update(self, event):
        pred = event.get_data()
        print(pred)
        if pred["type"] != "prediction":
            return None
        p = Prediction.from_redis(self._r, pred["id"])
        if p:
            p.update_arrival_time(
                pred["attributes"]["arrival_time"]
                or pred["attributes"]["departure_time"]
            )
            print(p.to_dict())
            p.add_to_redis(self._r)
            self.publish_update(p.get_route_list_name())
            if DEBUG:
                print("Updated prediction: ", p.to_short_string())
        else:
            if DEBUG:
                print("No prediction to update")

    def apply_remove(self, event):
        pred = event.get_data()
        if pred["type"] != "prediction":
            return None
        p = Prediction.from_redis(self._r, pred["id"])
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
        return (
            pred["attributes"]["arrival_time"] or pred["attributes"]["departure_time"]
        )

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
        for pred in self.get_next_two_predictions("Green", "1", now):
            s += pred.to_string(now) + "\n"
        s += "\n"

        s += "Green Line South\n"
        s += "----------------\n"
        for pred in self.get_next_two_predictions("Green", "0", now):
            s += pred.to_string(now) + "\n"
        return s

    def get_next_two_predictions(self, route, direction_str, now=datetime.now(tzutc())):
        preds = map(
            lambda id: Prediction.from_redis(self._r, id),
            self._r.smembers(create_route_list_name(route, direction_str)),
        )
        return sorted(
            filter(
                lambda pred: pred.get_arrival_time() > now
                and (pred.get_arrival_time() - now).seconds > 60,
                preds,
            )
        )[:2]

    def get_all_line_details(self, now=datetime.now(tzutc())):
        predictions = {}
        for line in LINES_TO_WATCH:
            for dir_str in ["1", "0"]:
                predictions[line + "_" + dir_str] = list(
                    map(
                        lambda p: p.to_dict(),
                        self.get_next_two_predictions(line, dir_str, now),
                    )
                )
        return predictions

    def acquire_lock(self):
        return self._r.lock(MBTA_LOCK_KEY)
