import dateutil.parser
from dateutil.tz import tzutc
from datetime import datetime


PRED_ID = "pred_id"
ROUTE_NAME = "route_name"
DIRECTION = "direction"
ARRIVAL_TIME = "arrival_time"


def create_route_list_name(route, direction):
    return str(route) + str(direction)


class Prediction:
    def __init__(self, pred_id, route, direction_str, arrival_time_str):
        self._pred_id = pred_id
        self._route = route
        self._direction = int(direction_str)
        self._arrival_time = dateutil.parser.parse(arrival_time_str)

    def __lt__(self, other):
        return self._arrival_time < other._arrival_time

    def update_arrival_time(self, new_time):
        if new_time is not None:
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
        elif(self._route == "Red"):
            destination = "Alewife" if self._direction == 1 else "Ashmont/BT"
        else:
            destination = "Lechmere" if self._direction == 1 else "Heath St"
        return "{} {} min".format(
            destination,
            ((self._arrival_time - now).seconds // 60) % 60
        )

    def to_dict(self):
        return {
            PRED_ID: self._pred_id,
            ROUTE_NAME: self._route,
            DIRECTION: self._direction,
            ARRIVAL_TIME: self._arrival_time.isoformat()
        }

    def get_route_list_name(self):
        return create_route_list_name(self._route, self._direction)

    def add_to_redis(self, r):
        # TODO: Race conditions??? Pipeline???
        r.hmset(self._pred_id, self.to_dict())
        r.sadd(self.get_route_list_name(), self._pred_id)

    def remove_from_redis(self, r):
        # TODO: Race conditions??? Pipeline???
        r.srem(self.get_route_list_name(), self._pred_id)
        r.delete(self._pred_id)

    @classmethod
    def from_redis(class_object, r, id):
        if r.exists(id):
            m = r.hgetall(id)
            return class_object(m[PRED_ID], m[ROUTE_NAME], m[DIRECTION], m[ARRIVAL_TIME])
        else:
            return None
