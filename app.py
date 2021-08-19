import falcon
import falcon.asgi

import json

from mbtastate import MBTAState
from buttonstate import ButtonState
from redis import Redis

class TestResource:
    async def on_get(self, req, resp):
        resp.text = json.dumps("Hello!")

class NamedResource:
    async def on_get(self, req, resp, name):
        resp.text = json.dumps("Hello " + name + "!")

class WebLineDetails:
    def __init__(self, mbta_state):
        self.mbta_state = mbta_state

    async def on_get(self, req, resp):
        resp.text = json.dumps(mbta_state.get_all_line_details())

class WebButton:
    def __init__(self, button_state):
        self.button_state = button_state

    async def on_post(self, req, resp, press):
        if press == "single":
            self.button_state.single_click()
            self.button_state.flag_update()
        elif press == "double":
            self.button_state.double_click()
            self.button_state.flag_update()
        resp.status_code = 200

app = falcon.asgi.App()
test = TestResource()
app.add_route('/api/test', test)

named = NamedResource()
app.add_route('/api/test/{name}', named)

r = Redis(host="127.0.0.1", port="6379", charset="utf-8", decode_responses=True)
mbta_state = MBTAState(r)
web_line_details = WebLineDetails(mbta_state)
app.add_route('/api/lines', web_line_details)

button_state = ButtonState(r)
web_button = WebButton(button_state)
app.add_route('/api/button/{press}', web_button)