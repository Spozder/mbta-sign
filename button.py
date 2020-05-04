from fliclib import ClickType
import fliclib
from redislite import Redis


BUTTON_KEY = "button"
SINGLE_OFFSET = 0
DOUBLE_OFFSET = 1
HOLD_OFFSET = 2

UPDATE_KEY = "update"

# Button Stuff


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


def on_single_click(state):
    state.single_click()
    state.flag_update()


def on_double_click(state):
    state.double_click()
    state.flag_update()


def on_hold(state):
    state.hold()
    state.flag_update()


def on_up(state):
    if state.release():
        state.flag_update()


button_handling_dict = {
    ClickType.ButtonSingleClick: on_single_click,
    ClickType.ButtonDoubleClick: on_double_click,
    ClickType.ButtonHold: on_hold,
    ClickType.ButtonUp: on_up
}


def on_button_press_creator(state):
    def on_button_press(channel, click_type, was_queued, time_diff):
        print("Button Pressed!")
        if click_type in button_handling_dict:
            button_handling_dict[click_type](state)
        else:
            print("Unknown click type: {}".format(click_type))
    return on_button_press


def got_verified_button(bd_addr, state):
    cc = fliclib.ButtonConnectionChannel(bd_addr)

    # Add button event handlers
    cc.on_button_single_or_double_click_or_hold = on_button_press_creator(
        state)
    cc.on_button_up_or_down = on_button_press_creator(state)

    button_client.add_connection_channel(cc)


def got_flic_server_info_factory(state):
    def got_flic_server_info(info):
        for bd_addr in info["bd_addr_of_verified_buttons"]:
            got_verified_button(bd_addr, state)
    return got_flic_server_info


button_state = ButtonState()
button_client = fliclib.FlicClient("localhost")
button_client.get_info(got_flic_server_info_factory(button_state))

button_client.handle_events()
