import dateutil.parser
from dateutil.tz import tzutc
from datetime import datetime


PRED_ID = "pred_id"
ROUTE_NAME = "route_name"
DIRECTION = "direction"
ARRIVAL_TIME = "arrival_time"
TRIP_ID = "trip_id"
HEADSIGN = "headsign"

HEADSIGN_LOOKUP = "headsigns"

DESTINATION_LOOKUP = {
    "Orange": {"1": "Oak Grove", "0": "Forest Hills"},
    "Red": {"1": "Alewife", "0": "Ashmont/BT"},
    "741": {"1": "South Statn", "0": "Boston Logan"},
    "742": {"1": "South Statn", "0": "Drydock Ave"},
    "743": {"1": "South Statn", "0": "Chelsea"},
    "746": {"1": "South Statn", "0": "SL Way"},
    "Blue": {"1": "Wonderland", "0": "Bowdoin"},
    "Green-E": {"1": "Lechmere", "0": "Heath St"},
    "Green-D": {"1": "idk", "0": "idk"},
    "Green-C": {"1": "idk", "0": "idk"},
    "Green-B": {"1": "idk", "0": "idk"},
}


def create_route_list_name(route, direction):
    if str(route) in ["741", "742", "743", "746"]:
        return "Silver" + str(direction)
    if str(route) in ["Green-E", "Green-D", "Green-C", "Green-B"]:
        return "Green" + str(direction)
    return str(route) + str(direction)


class Prediction:
    def __init__(
        self, pred_id, route, direction_str, trip_id, arrival_time_str, headsign
    ):
        self._pred_id = pred_id
        self._route = route
        self._direction = int(direction_str)
        self._arrival_time = dateutil.parser.parse(arrival_time_str)
        self._trip_id = trip_id
        self._headsign = headsign or DESTINATION_LOOKUP[route][str(direction_str)]

    def __lt__(self, other):
        return self._arrival_time < other._arrival_time

    def update_arrival_time(self, new_time):
        if new_time is not None:
            self._arrival_time = dateutil.parser.parse(new_time)

    def set_headsign(self, new_headsign):
        self._headsign = new_headsign

    def get_trip_id(self):
        return self._trip_id

    def get_arrival_time(self):
        return self._arrival_time

    def get_route(self):
        return self._route

    def get_direction(self):
        return self._direction

    def remove(self):
        self._pred_id = "-REMOVED"

    def to_string(self, now=datetime.now(tzutc())):
        return (
            "Prediction for {} line going {} (ID {}): {} ({} minutes from now)".format(
                self._route,
                ("North" if self._direction == 1 else "South"),
                self._pred_id.split("-")[1]
                if self._pred_id.split("-")[1] != "ADDED"
                else self._pred_id.split("-")[2],
                self._arrival_time.strftime("%B %d, %Y - %l:%M:%S %p"),
                ((self._arrival_time - now).seconds // 60) % 60,
            )
        )

    def to_short_string(self, now=datetime.now(tzutc())):
        return "{} {} min".format(
            self._headsign, ((self._arrival_time - now).seconds // 60) % 60
        )

    def to_dict(self):
        return {
            PRED_ID: self._pred_id,
            ROUTE_NAME: self._route,
            DIRECTION: self._direction,
            TRIP_ID: self._trip_id,
            ARRIVAL_TIME: self._arrival_time.isoformat(),
            HEADSIGN: self._headsign,
        }

    def get_route_list_name(self):
        return create_route_list_name(self._route, self._direction)

    def add_to_redis(self, r):
        # TODO: Race conditions??? Pipeline???
        r.hmset(self._pred_id, self.to_dict())
        print(self.to_dict())
        r.sadd(self.get_route_list_name(), self._pred_id)

    def remove_from_redis(self, r):
        # TODO: Race conditions??? Pipeline???
        r.srem(self.get_route_list_name(), self._pred_id)
        r.delete(self._pred_id)

    @classmethod
    def from_redis(class_object, r, id):
        if r.exists(id):
            m = r.hgetall(id)
            trip_id = m[TRIP_ID]
            headsign = r.hget(HEADSIGN_LOOKUP, trip_id)
            return class_object(
                m[PRED_ID],
                m[ROUTE_NAME],
                m[DIRECTION],
                m[TRIP_ID],
                m[ARRIVAL_TIME],
                headsign or m[HEADSIGN],
            )
        else:
            return None

    @classmethod
    def set_headsign_in_redis(class_object, r, trip_id, headsign):
        return r.hset(HEADSIGN_LOOKUP, trip_id, headsign)
