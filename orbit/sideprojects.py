"""Side projects: at most five active cards, the rest parked.

A card can be just an idea (folder None) until a folder is linked. Stored in
~/.config/orbit/sideprojects.json. Stdlib only; every function but load/save is pure so it can be asserted.
"""

import json
import os
import time

PATH = os.path.expanduser("~/.config/orbit/sideprojects.json")
CAP = 5


def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save(cards):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cards, f, indent=1)
    os.replace(tmp, PATH)


def add(cards, name, now=None):
    now = now or int(time.time())
    c = {"id": "%d-%d" % (now, len(cards)), "name": name, "folder": None,
         "next": "", "suggest": "", "active": False, "touched": now}
    cards.append(c)
    return activate(cards, c["id"], now)


def activate(cards, cid, now=None):
    """Make a card active; if that makes six, park the one touched longest ago."""
    now = now or int(time.time())
    for c in cards:
        if c["id"] == cid:
            c["active"], c["touched"] = True, now
    active = sorted((c for c in cards if c["active"] and c["id"] != cid),
                    key=lambda c: c["touched"])
    while len(active) + 1 > CAP:
        active.pop(0)["active"] = False
    return cards


def park(cards, cid):
    for c in cards:
        if c["id"] == cid:
            c["active"] = False
    return cards


def owns(card, cwd):
    """Is a session running in `cwd` working on this card?"""
    f = card.get("folder")
    return bool(f and cwd and (cwd == f or cwd.startswith(f.rstrip("/") + "/")))
