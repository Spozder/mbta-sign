from redis import Redis

import requests
import time

CUSTOM_TEXT_KEY = "custom"

r = Redis(host="127.0.0.1", port="6379", charset="utf-8", decode_responses=True)

while True:
    time.sleep(5)
    try:
        data = requests.get("https://afoolishqueue.com/pop").json()
    except:
        print("Queue unavailable - retrying")
        time.sleep(10)
        continue
    if data and data["text"]:
        r.publish(CUSTOM_TEXT_KEY, data["text"])
