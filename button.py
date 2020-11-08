from buttonstate import ButtonState
from fliclib import ClickType
import fliclib

from redis import Redis

# Button Stuff

DEBUG = False


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


def no_op(state):
    pass


button_handling_dict = {
    ClickType.ButtonSingleClick: on_single_click,
    ClickType.ButtonDoubleClick: on_double_click,
    ClickType.ButtonHold: on_hold,
    ClickType.ButtonUp: on_up,
    ClickType.ButtonDown: no_op
}


def on_button_press_creator(state):
    def on_button_press(channel, click_type, was_queued, time_diff):
        if DEBUG:
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


button_state = ButtonState(
    Redis(host='127.0.0.1', port='6379',
          charset="utf-8", decode_responses=True))
button_client = fliclib.FlicClient("localhost")
button_client.get_info(got_flic_server_info_factory(button_state))

button_client.handle_events()
