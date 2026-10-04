"""Everything personal about one setup, read from ~/.config/orbit/config.json.

No file means: index this Mac only, no themes, no GitHub owners. See
config.example.json for every key. Stdlib only.
"""

import json
import os
import socket

PATH = os.path.expanduser("~/.config/orbit/config.json")


def load(path=PATH):
    try:
        with open(path) as f:
            return json.load(f)
    except OSError:
        return {}
    except ValueError as e:
        raise SystemExit("orbit: %s is not valid JSON: %s" % (path, e))


_c = load()

# The label this Mac's repos carry in the index, e.g. "laptop".
LOCAL = _c.get("local") or socket.gethostname().split(".")[0].lower()
# Other Macs: {label: ssh host}. orbit runs `ssh <host> /usr/bin/python3 -`.
HOSTS = dict(_c.get("hosts") or {})
# GitHub owners whose repos are yours. Another owner's clone is THIRD-PARTY.
# Empty means "not configured": nothing is marked third-party.
MINE = tuple(_c.get("mine") or ())
# {THEME: [name prefixes]}; first match wins, file order is display order.
THEMES = {t: tuple(p) for t, p in (_c.get("themes") or {}).items()}
# Home-relative folders to index even without a .git (a notes vault, say).
EXTRA_ROOTS = tuple(_c.get("extra_roots") or ())
# Home-relative paths never scanned (huge runtime data inside a repo).
IGNORE = tuple(_c.get("ignore") or ())
# Whether `orbit refresh` asks the gh CLI for your GitHub repos (gaps view).
GITHUB = _c.get("github", True)

BUILTIN = ("UNTAGGED", "THIRD-PARTY")
ALL_HOSTS = [LOCAL] + [h for h in HOSTS if h != LOCAL]
