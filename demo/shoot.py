"""Build a made-up two-Mac setup and screenshot every orbit tab.

    .venv/bin/python demo/shoot.py            # PNGs land in docs/screenshots/

Nothing here touches your real index or your real home: HOME points at a
throwaway folder before orbit is imported, so every path orbit computes lands
inside it. The repos, sessions and cards are invented. The second Mac
("studio") is a second fake home merged in-process instead of over ssh; the
index and the UI are the real ones.

The explain screenshot makes one real `claude -p` call about a fake file. With
--no-ask it is skipped. Needs textual (the orbit venv) and Google Chrome,
which turns the SVG screenshots into PNGs.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "screenshots")
REAL_HOME = os.path.expanduser("~")
DEMO = tempfile.mkdtemp(prefix="orbit-demo-")
LAPTOP, STUDIO = os.path.join(DEMO, "laptop"), os.path.join(DEMO, "studio")
SVG = os.path.join(DEMO, "svg")
NOW = int(time.time())
SIZE = (150, 40)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SERVER_PY = '''"""HTTP entry point for the Acme billing API."""

import random
import time

from .billing import charge, Declined

MAX_TRIES = 3


def with_retry(fn, *args, tries=MAX_TRIES, base=0.2):
    """Call fn, retrying on network errors with jittered backoff.
    A declined card is an answer, not an error: never retried."""
    for attempt in range(1, tries + 1):
        try:
            return fn(*args)
        except Declined:
            raise
        except ConnectionError:
            if attempt == tries:
                raise
            time.sleep(base * 2 ** attempt * random.uniform(0.5, 1.5))


def handle_charge(request):
    customer = request.json["customer"]
    cents = int(request.json["amount_cents"])
    if cents <= 0:
        return {"error": "amount must be positive"}, 400
    try:
        receipt = with_retry(charge, customer, cents)
    except Declined as e:
        return {"error": "declined", "reason": str(e)}, 402
    return {"receipt": receipt.id}, 201
'''

# home-relative path -> (text, age in seconds)
LAPTOP_FILES = {
    "code/acme-api/src/server.py": (SERVER_PY, 600),
    "code/acme-api/src/billing.py": ("class Declined(Exception):\n    pass\n\n\ndef charge(customer, cents):\n    ...\n", 4000),
    "code/acme-api/tests/test_server.py": ("from src.server import with_retry\n\n\ndef test_retry_gives_up():\n    ...\n", 700),
    "code/acme-api/README.md": ("# acme-api\n\nBilling API. `make dev` runs it on :8000.\n", 90000),
    "code/acme-api/pyproject.toml": ('[project]\nname = "acme-api"\nversion = "0.4.0"\n', 90000),
    "code/acme-dashboard/src/App.tsx": ("export function App() {\n  return <Invoices retry={3} />;\n}\n", 7200),
    "code/acme-dashboard/package.json": ('{"name": "acme-dashboard", "private": true}\n', 200000),
    "code/toy-raytracer/src/main.rs": ("fn main() {\n    let scene = Scene::spheres(3);\n    scene.render(\"out.ppm\");\n}\n", 3 * 86400),
    "code/toy-raytracer/Cargo.toml": ('[package]\nname = "toy-raytracer"\n', 9 * 86400),
    "learn-sql/queries.sql": ("-- window functions\nSELECT name, rank() OVER (ORDER BY total DESC) FROM orders;\n", 2 * 86400),
    "learn-sql/notes.md": ("# SQL notes\n\nA window function sees other rows without grouping them away.\n", 2 * 86400),
    "dotfiles/zshrc": ("export EDITOR=nvim\nalias gs='git status'\n", 20 * 86400),
    "src/tiny-http/server.go": ("package main\n\n// retry is handled by the caller\nfunc main() {}\n", 40 * 86400),
}
STUDIO_FILES = {
    "acme-ml/train.py": ("def train(cfg):\n    # retry the epoch once on CUDA out-of-memory with half the batch\n    ...\n", 1800),
    "acme-ml/data/loader.py": ("def batches(path, size):\n    ...\n", 5 * 86400),
    "home-server/backup.sh": ("#!/bin/sh\n# nightly: retry rsync up to 3 times\nrsync -a ~/photos nas:/backup/\n", 86400),
    "home-server/docker-compose.yml": ("services:\n  jellyfin:\n    image: jellyfin/jellyfin\n", 30 * 86400),
    "notes/ideas.md": ("# Ideas\n\n- plant watering bot\n- retry budget per customer\n", 4 * 3600),
}
REMOTES = {
    "code/acme-api": "git@github.com:you/acme-api.git",
    "code/acme-dashboard": "git@github.com:you/acme-dashboard.git",
    "code/toy-raytracer": "https://github.com/you/toy-raytracer.git",
    "dotfiles": "git@github.com:you/dotfiles.git",
    "src/tiny-http": "https://github.com/someone-else/tiny-http.git",
    "acme-ml": "git@github.com:you/acme-ml.git",
    "home-server": "git@github.com:you/home-server.git",
}
NO_REMOTE = ("learn-sql",)

CONFIG = {
    "local": "laptop",
    "mine": ["you"],
    "themes": {"WORK": ["acme-"], "LEARNING": ["toy-", "learn-"]},
    "extra_roots": ["notes"],
    "github": False,
}


def write(home, files):
    for rel, (text, age) in files.items():
        p = os.path.join(home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        os.utime(p, (NOW - age, NOW - age))
    for repo, url in list(REMOTES.items()) + [(r, None) for r in NO_REMOTE]:
        if not os.path.isdir(os.path.join(home, repo)):
            continue
        g = os.path.join(home, repo, ".git")
        os.makedirs(g, exist_ok=True)
        with open(os.path.join(g, "HEAD"), "w") as f:
            f.write("ref: refs/heads/main\n")
        if url:
            with open(os.path.join(g, "config"), "w") as f:
                f.write('[remote "origin"]\n\turl = %s\n' % url)


def build_homes():
    write(LAPTOP, LAPTOP_FILES)
    write(STUDIO, STUDIO_FILES)
    cfg = os.path.join(LAPTOP, ".config", "orbit")
    os.makedirs(cfg)
    with open(os.path.join(cfg, "config.json"), "w") as f:
        json.dump(CONFIG, f)
    cards = [
        {"id": "1", "name": "toy-raytracer", "folder": os.path.join(LAPTOP, "code/toy-raytracer"),
         "next": "soft shadows", "suggest": "Add an area light, then sample it 16x",
         "active": True, "touched": NOW - 3 * 3600},
        {"id": "2", "name": "learn-sql", "folder": os.path.join(LAPTOP, "learn-sql"),
         "next": "window functions chapter", "suggest": "", "active": True, "touched": NOW - 86400},
        {"id": "3", "name": "plant watering bot", "folder": None,
         "next": "buy a soil moisture sensor", "suggest": "", "active": True, "touched": NOW - 5 * 86400},
        {"id": "4", "name": "pixel-art editor", "folder": None,
         "next": "", "suggest": "", "active": False, "touched": NOW - 40 * 86400},
    ]
    with open(os.path.join(cfg, "sideprojects.json"), "w") as f:
        json.dump(cards, f)
    for c in cards:                     # a card's "touched" includes its folder's mtime
        if c["folder"]:
            os.utime(c["folder"], (c["touched"], c["touched"]))
    days = [time.strftime("%Y-%m-%d", time.localtime(NOW - d * 86400)) for d in range(4, 0, -1)]
    progress = {"kv": {"passed": {str(n): "unaided" for n in range(1, 9)}, "pasted": [], "shown": []},
                "lru": {"passed": {"1": "unaided", "2": "unaided"}, "pasted": [], "shown": []},
                "days": days}
    with open(os.path.join(cfg, "ladder.json"), "w") as f:
        json.dump(progress, f)
    os.makedirs(os.path.join(LAPTOP, "ladder"))
    shutil.copy(os.path.join(REPO, "ladder", "lru", ".solutions", "02.py"),
                os.path.join(LAPTOP, "ladder", "lru.py"))


# ------------------------------------------------------- fake live sessions

RULE = "─" * 70


def screen(*lines):
    return "\n".join(list(lines) + ["", RULE, "❯ ", RULE, "  ⏵⏵ accept edits on", ""])


SESSIONS = [
    ({"session_id": "s1", "state": "needs_you", "waiting_since": NOW - 140, "tty": "/dev/ttys004",
      "project": "toy-raytracer", "title": "Speed up the render loop",
      "cwd": os.path.join(LAPTOP, "code/toy-raytracer")},
     "\n".join(["⏺ I'll build in release mode to compare timings.", "",
                RULE, " Bash command", "", "   cargo build --release", "   Build the optimised binary",
                "", " Do you want to proceed?", " ❯ 1. Yes",
                "   2. Yes, and don't ask again for cargo build commands",
                "   3. No, and tell Claude what to do differently", ""])),
    ({"session_id": "s2", "state": "idle", "waiting_since": NOW - 610, "tty": "/dev/ttys002",
      "project": "acme-api", "title": "Retry card charges on network errors",
      "cwd": os.path.join(LAPTOP, "code/acme-api")},
     screen("⏺ Update(src/server.py)", "  ⎿  Updated src/server.py with 14 additions",
            "⏺ Bash(pytest -q)", "  ⎿  12 passed in 0.41s",
            "⏺ Done. with_retry() retries ConnectionError up to 3 times",
            "  with jittered backoff; a Declined card is never retried.",
            "  12/12 tests pass.")),
    ({"session_id": "s3", "state": "busy", "tty": "/dev/ttys006",
      "project": "acme-dashboard", "title": "Invoice table pagination",
      "cwd": os.path.join(LAPTOP, "code/acme-dashboard")},
     screen("⏺ Read(src/App.tsx)", "  ⎿  Read 42 lines",
            "⏺ Update(src/App.tsx)", "  ⎿  Updated src/App.tsx with 9 additions and 2 removals",
            "", "✳ Paginating… (48s · ↓ 1.2k tokens)")),
]


def patch_live_sessions():
    """The sessions tab normally reads pulse files and real Terminal windows.
    Here both answer with the canned sessions above."""
    from orbit import jump
    from orbit import sessions as S
    rows = [dict(r, pid=os.getpid(), last_event_at=NOW) for r, _ in SESSIONS]
    S.load = lambda: [dict(r) for r in rows]
    jump.screens = lambda ttys: "".join("\x02%s\x03%s" % (r["tty"], text)
                                        for r, text in SESSIONS if r["tty"] in ttys)
    jump.ping = lambda: None


# ------------------------------------------------------------------ index

def build_index():
    from orbit import config as C
    from orbit import db as D
    from orbit import refresh as R
    from orbit import scan as S
    R.run(bodies=True, gh=False, verbose=True)          # this Mac, the real way
    db = D.connect()
    D.merge_host(db, "studio", S.scan(STUDIO, list(C.EXTRA_ROOTS)),
                 R.meta_factory("studio", {}))
    home, R.HOME = R.HOME, STUDIO
    R.pull_local(db, R.pending_bodies(db, "studio"))
    R.HOME = home
    db.commit()
    db.close()
    # from here on the UI sees two Macs
    C.HOSTS = {"studio": "studio.local"}
    C.ALL_HOSTS = [C.LOCAL, "studio"]


# ------------------------------------------------------------------ shots

def node_where(tree, test):
    stack = [tree.root]
    while stack:
        n = stack.pop(0)
        if test(n):
            return n
        stack.extend(n.children)
    return None


async def shoot(ask):
    from textual.widgets import Tree, TextArea
    from textual.widgets.text_area import Selection
    from orbit.tui import Orbit

    app = Orbit()
    shots = []

    def snap(name):
        app.save_screenshot(name + ".svg", SVG)
        shots.append(name)

    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause(1)
        projects = app.query_one("#projects", Tree)
        repo = node_where(projects, lambda n: n.data and n.data[0] == "repo"
                          and n.data[1]["name"] == "acme-api")
        projects.move_cursor(repo)
        await pilot.pause(0.3)
        files = app.query_one("#files", Tree)
        src = node_where(files, lambda n: n.data == ("dir", "src/"))
        src.expand()
        await pilot.pause(0.3)
        files.move_cursor(node_where(files, lambda n: n.data and n.data[0] == "file"
                                     and n.data[2] == "src/server.py"))
        files.focus()
        await pilot.pause(0.5)
        snap("files")

        await pilot.press("s")
        await pilot.pause(0.2)
        await pilot.press(*"retry")
        await pilot.pause(1)
        snap("search")
        await pilot.press("escape")
        await pilot.pause(0.3)

        if ask:
            ta = app.query_one("#code", TextArea)
            ta.selection = Selection((10, 0), (22, 0))      # with_retry, lines 11-22
            ta.focus()
            os.environ["HOME"] = REAL_HOME                  # claude needs your login
            app.action_ask()
            for _ in range(240):
                await pilot.pause(0.5)
                head = str(app.query_one("#answerhead").render())
                if "esc to close" in head or "failed" in head or "timed out" in head:
                    break
            os.environ["HOME"] = LAPTOP
            await pilot.pause(0.5)
            snap("explain")
            app.action_close_answer()

        app.action_inbox()                                  # i: the session waiting longest
        await pilot.pause(2.5)
        snap("sessions")
        app.action_tab("t-side")
        await pilot.pause(0.5)
        snap("side-projects")
        app.action_tab("t-ladder")
        await pilot.pause(0.5)
        snap("ladder")
    return shots


def to_png(name):
    """Chrome renders the SVG at 2x; Textual's SVG names its own web font."""
    import re
    svg = os.path.join(SVG, name + ".svg")
    with open(svg) as f:
        w, h = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', f.read()).groups()
    out = os.path.join(OUT, name + ".png")
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.Popen([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                          "--no-first-run", "--user-data-dir=" + os.path.join(DEMO, "chrome"),
                          "--force-device-scale-factor=2",
                          "--window-size=%d,%d" % (round(float(w)), round(float(h))),
                          "--screenshot=" + out, "file://" + svg],
                         env=dict(os.environ, HOME=REAL_HOME),   # exits at once under the fake one
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Chrome 154 writes the file and then does not always exit: wait for the
    # file, not for the process
    for _ in range(120):
        if p.poll() is not None or (os.path.exists(out) and time.time() - os.path.getmtime(out) > 1):
            break
        time.sleep(0.5)
    p.kill()
    p.wait()
    if not os.path.exists(out):
        raise SystemExit("Chrome made no screenshot of " + svg)
    return out


def main():
    os.environ["HOME"] = LAPTOP                     # before orbit is imported
    os.chdir(DEMO)                                  # claude -p runs here, not in a real repo
    sys.path.insert(0, REPO)
    build_homes()
    patch_live_sessions()
    build_index()
    os.makedirs(SVG)
    shots = asyncio.run(shoot(ask="--no-ask" not in sys.argv))
    os.makedirs(OUT, exist_ok=True)
    for name in shots:
        print(to_png(name))
    print("\nSVG sources (text, so they can be leak-scanned): %s" % SVG)


if __name__ == "__main__":
    main()
