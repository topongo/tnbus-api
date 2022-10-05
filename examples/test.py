from tnbus import TNBus, API, By, Cond
from datetime import datetime
from pytz import timezone

with open("../src/tnbus/auth") as f:
    t = TNBus(API(f.read().strip()), tz="CET")  # , preload=json.load(d))

# 25205x borino
# 25045x valoni discesa
# 25040z salè salita
# 25050- sommarive
# 21745z portaquila salita

stops = {}
for i in t.get(
        TNBus.Stop,
        *((By.ID, i) for i in ("25205x", "25045x", "25050-", "21745z")),
        cond_mode=Cond.OR,
        override_unique=True):
    stops[i.id] = i

assoc = {
    "25205x": "BRN",
    "25045x": "PVVLN",
    "25050-": "PVSL",
    "21745z": "VNZPRTQL"
}

from json import dump
from time import sleep

while True:
    data = []
    for st in stops.values():
        trs = st.load_trips(t, limit=3)
        ok, ok_a = None, None
        for tr in trs:
            a = st.get_trip_stop(tr).arrival.replace(tzinfo=timezone("cet"))
            if ok is not None:
                if ok_a > a > datetime.now().time():
                    ok, ok_a = tr, a
            else:
                ok, ok_a = tr, a

        if ok is None:
            arr = delay = "N/A"
        else:
            delay = ok.delay or 0
            arr = st.get_trip_stop(ok).arrival

        data.append({
            "name": assoc[st.id],
            "time": arr.strftime("%H:%M"),
            "delay": delay,
            "is_delayed": delay != "N/A" and delay != 0
        })

    dump(data,
         open("/mnt/data/documents/uni/advancedProgramming/Bo_SE_website/templates/static/busses.json", "w+"),
         indent=4)
    print(data)
    sleep(15)
