"""orbit self-check. Asserts only -- no framework, no fixtures.

    python3 test_orbit.py
"""
import os
import shlex
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orbit import config as C
from orbit import db as D
from orbit import jump
from orbit import scan as S
from orbit.refresh import theme_for

# A fixed setup, whatever ~/.config/orbit/config.json says on this machine.
C.LOCAL, C.HOSTS = "laptop", {"box": "box.local"}


def t_ignore_rules():
    """Junk folders stay out of the index; "ignore" paths are prefix rules."""
    S.IGNORE_PATHS = ("tool/runtime",)
    try:
        assert S.ignored_path("tool/runtime")
        assert S.ignored_path("tool/runtime/cache/x.json")
        assert not S.ignored_path("tool/runtimes"), "a prefix of a name is not a match"
        assert not S.ignored_path("tool/bin/run")
    finally:
        S.IGNORE_PATHS = ()
    assert ".build" in S.IGNORE_NAMES, "one Swift .build was 2.0 GB of noise"
    assert "node_modules" in S.IGNORE_NAMES
    assert "Pictures" in S.PRUNE_ROOT, "photo libraries are 100k+ files"
    assert "Downloads" not in S.PRUNE_ROOT, "people clone repos into Downloads"


def t_config_load():
    """No file is fine; a broken file stops orbit with a message, it is
    never silently ignored."""
    import tempfile
    tmp = tempfile.mkdtemp()
    assert C.load(os.path.join(tmp, "missing.json")) == {}
    bad = os.path.join(tmp, "bad.json")
    with open(bad, "w") as f:
        f.write('{"hosts": {"box": "box.local",}}')
    try:
        C.load(bad)
        assert False, "bad JSON was accepted"
    except SystemExit as e:
        assert "not valid JSON" in str(e), e


def t_is_text():
    for name in ("a.py", "b.ts", "Makefile", "notes.md", "conf.yaml"):
        assert S.is_text(name), name
    for name in ("x.png", "y.dmg", "z.bin", "model.safetensors"):
        assert not S.is_text(name), name


def t_paths_with_spaces():
    """'~/my project' on another Mac must survive every quoting layer, and its
    ~ must reach the remote shell unquoted so that shell expands it."""
    import subprocess
    import tempfile
    d = jump.abs_dir("box", "my project", "src/app")
    assert d == "~/my project/src/app", d
    argv = jump.remote_cmd("box", d, "exec claude")
    assert argv[:3] == ["ssh", "-t", "box.local"], argv
    # the whole zsh -lc payload must survive one shell-level split intact
    inner = shlex.split(argv[3])
    assert inner[0] == "zsh" and inner[1] == "-lc", inner
    # ...and land in the right folder when a shell runs it with another HOME
    home = tempfile.mkdtemp()
    os.makedirs(os.path.join(home, "my project", "src", "app"))
    out = subprocess.run(["/bin/sh", "-c", inner[2].replace("exec claude", "pwd -P")],
                         env={"HOME": home, "PATH": "/usr/bin:/bin"},
                         stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
    want = os.path.realpath(os.path.join(home, "my project", "src", "app"))
    assert out == want, (out, want)


def t_abs_dir_hosts():
    assert jump.abs_dir("laptop", "code/app") == os.path.expanduser("~/code/app")
    assert jump.abs_dir("box", "notes", "") == "~/notes"
    assert jump.remote_path("box", "~/notes") == "box.local:~/notes"


def t_themes():
    themes = {"WORK": ("acme-",), "FUN": ("toy-",)}
    mine = ("me",)
    assert theme_for("box", "acme-api", "acme-api", None, {}, themes, mine) == "WORK"
    assert theme_for("box", "code/Toy-ray", "Toy-ray", None, {}, themes, mine) == "FUN"
    assert theme_for("box", "misc", "misc", None, {}, themes, mine) == "UNTAGGED"
    # someone else's clone is third-party, even when named like a theme
    other = "https://github.com/someone/acme-fork.git"
    assert theme_for("box", "acme-fork", "acme-fork", other, {}, themes, mine) == "THIRD-PARTY"
    # ...but your own remote is not (owner match ignores case)
    assert theme_for("box", "toy-ray", "toy-ray", "git@github.com:Me/toy-ray.git",
                     {}, themes, mine) == "FUN"
    # no owners configured: nothing can be called third-party
    assert theme_for("box", "acme-fork", "acme-fork", other, {}, themes, ()) == "WORK"
    # an explicit tag beats everything
    assert theme_for("box", "acme-fork", "acme-fork", other,
                     {"box:acme-fork": "FUN"}, themes, mine) == "FUN"


def t_fts_query_escaping():
    """`orbit find hash-chained` died with "no such column: chained" because
    FTS5 reads '-' as NOT and 'a:b' as a column filter."""
    assert D.fts_query("hash-chained") == '"hash-chained"'
    assert D.fts_query('say "hi"') == '"say ""hi"""'
    assert D.fts_query("foo:bar") == '"foo:bar"'
    assert D.fts_query("=launchd AND plist") == "launchd AND plist", "= opts into raw FTS5"


def t_remote_nwo():
    """rstrip('.git') strips any trailing . g i or t -- chat-bot.git became
    chat-bo, so `orbit gaps` claimed cloned repos were missing."""
    assert D.remote_nwo("https://github.com/Someone/chat-bot.git") == "someone/chat-bot"
    assert D.remote_nwo("git@github.com:Someone/budget-app.git") == "someone/budget-app"
    assert D.remote_nwo("https://github.com/Someone/notes") == "someone/notes"
    assert D.remote_nwo(None) is None


def t_gaps_are_honest():
    """A repo that is cloned must never be listed as missing."""
    if not os.path.exists(D.DB_PATH):
        print("  (skipped: no index built yet)")
        return
    db = D.connect()
    missing, never = D.gaps(db)
    cloned = {D.remote_nwo(r["remote"]) for r in D.repos(db)}
    for g in missing:
        assert g["nwo"].lower() not in cloned, "%s is cloned" % g["nwo"]
    for r in never:
        assert not r["remote"]
    db.close()


def t_pane_clamp():
    """Two panes dragged wide on a narrow window must not push the preview
    off-screen."""
    try:
        from orbit.tui import clamp_pane, MIN_PANE, MAX_PANE, MIN_PREVIEW
    except ImportError:
        print("  (skipped: textual not installed for this interpreter)")
        return
    assert clamp_pane(44, 34, 160) == 44, "normal case is untouched"
    assert clamp_pane(2, 34, 160) == MIN_PANE
    assert clamp_pane(999, 34, 300) == MAX_PANE
    # narrow terminal: the preview keeps its floor
    w = clamp_pane(60, 34, 90)
    assert w + 34 + 2 + MIN_PREVIEW <= 90, w
    # both panes maxed on a tiny terminal still leaves room
    w = clamp_pane(999, MIN_PANE, 60)
    assert w + MIN_PANE + 2 + MIN_PREVIEW <= 60, w


def t_ask_prompt():
    """The prompt must name the real file, so the answer can talk about it
    rather than about a nameless snippet."""
    try:
        from orbit.tui import build_prompt, language_for
    except ImportError:
        print("  (skipped: textual not installed for this interpreter)")
        return
    assert language_for("a/b/c.py") == "python"
    assert language_for("x.tsx") == "javascript", "no tsx grammar; fall back"
    assert language_for("Makefile") is None, "unknown -> unhighlighted, not a crash"
    pr = build_prompt("box", "acme-api", "vision.py",
                      "import torch", 10, 20)
    assert "box:acme-api/vision.py" in pr
    assert "lines 10-20" in pr
    assert "import torch" in pr
    # whole-file form carries no line range
    assert "lines" not in build_prompt("laptop", "r", "f.py", "x").split("From")[1]


def t_index_pipeline():
    """scan -> merge -> pull bodies -> FTS5, end to end on a throwaway home."""
    import tempfile
    from orbit import refresh as R
    tmp = tempfile.mkdtemp()
    repo = os.path.join(tmp, "code", "acme-api")
    for d in (".git", "node_modules/dep", "src"):
        os.makedirs(os.path.join(repo, d))
    files = {"src/server.py": "def handler():\n    return 'hash-chained log'\n",
             "node_modules/dep/index.js": "hash-chained log",
             ".git/config": '[remote "origin"]\n\turl = git@github.com:me/acme-api.git\n',
             ".git/HEAD": "ref: refs/heads/main\n"}
    for rel, text in files.items():
        with open(os.path.join(repo, rel), "w") as f:
            f.write(text)
    db = D.connect(os.path.join(tmp, "index.db"))
    D.merge_host(db, "laptop", S.scan(tmp, []), R.meta_factory("laptop", {}))
    home, R.HOME = R.HOME, tmp
    try:
        assert R.pull_local(db, R.pending_bodies(db, "laptop")) == 1
    finally:
        R.HOME = home
    r = D.repos(db)[0]
    assert (r["host"], r["path"], r["branch"]) == ("laptop", "code/acme-api", "main"), dict(r)
    assert D.remote_nwo(r["remote"]) == "me/acme-api"
    hits = D.find_content(db, "hash-chained", limit=5)
    assert [h["path"] for h in hits] == ["src/server.py"], "node_modules must stay out"
    assert not R.pending_bodies(db, "laptop"), "a pulled body is not pulled again"
    db.close()


def t_inbox_order():
    """Needs-you beats finished; a fresh idle session is not in the inbox."""
    from orbit import sessions as SS
    rows = [
        {"session_id": "fin-old", "state": "idle", "waiting_since": 100},
        {"session_id": "fresh", "state": "idle"},
        {"session_id": "busy", "state": "busy"},
        {"session_id": "ask-new", "state": "needs_you", "waiting_since": 300},
        {"session_id": "ask-old", "state": "needs_you", "waiting_since": 200},
        {"session_id": "fin-new", "state": "idle", "waiting_since": 400},
    ]
    got = [r["session_id"] for r in SS.inbox(rows)]
    assert got == ["ask-old", "ask-new", "fin-old", "fin-new"], got


def t_changed_files_diff():
    """Edited files come from tool calls; the baseline is Claude Code's @v1 copy."""
    import hashlib
    import json
    import tempfile
    from orbit import sessions as SS
    tmp = tempfile.mkdtemp()
    old, new = os.path.join(tmp, "old.py"), os.path.join(tmp, "new.py")
    with open(old, "w") as f:
        f.write("a = 1\nb = 2\n")
    with open(new, "w") as f:
        f.write("fresh\n")
    SS.HISTORY = os.path.join(tmp, "hist")
    os.makedirs(os.path.join(SS.HISTORY, "sid"))
    with open(os.path.join(SS.HISTORY, "sid", hashlib.sha256(old.encode()).hexdigest()[:16]
                           + "@v1"), "w") as f:
        f.write("a = 1\n")
    tr = os.path.join(tmp, "t.jsonl")
    call = lambda name, p: json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": {"file_path": p}}]}})
    with open(tr, "w") as f:
        f.write("\n".join([call("Edit", old), call("Read", "/nope"),
                           call("Write", new), call("Edit", old)]) + "\n")
    assert SS.changed_files(tr) == [old, new], SS.changed_files(tr)
    d = SS.diff("sid", old)
    assert "--- before Claude" in d and "+b = 2" in d and "-a = 1" not in d, d
    assert "--- (new file)" in SS.diff("sid", new) and "+fresh" in SS.diff("sid", new)


def t_sideproject_cap():
    """Five active at most; the one touched longest ago gets parked."""
    from orbit import sideprojects as SP
    cards = []
    for i in range(5):
        SP.add(cards, "p%d" % i, now=100 + i)
    assert sum(c["active"] for c in cards) == 5
    SP.add(cards, "sixth", now=200)
    active = {c["name"] for c in cards if c["active"]}
    assert active == {"p1", "p2", "p3", "p4", "sixth"}, active
    SP.activate(cards, cards[0]["id"], now=300)          # unpark p0 -> p1 parks
    active = {c["name"] for c in cards if c["active"]}
    assert active == {"p0", "p2", "p3", "p4", "sixth"}, active
    SP.park(cards, cards[0]["id"])
    assert sum(c["active"] for c in cards) == 4
    card = {"folder": "/Users/x/proj"}
    assert SP.owns(card, "/Users/x/proj") and SP.owns(card, "/Users/x/proj/src")
    assert not SP.owns(card, "/Users/x/project2") and not SP.owns({"folder": None}, "/")


RULE = "─" * 40
SCREEN = "\n".join([
    "⏺ Bash(pytest)", "  14/14 passed", "", "✳ Concocting… (4m 6s)", "", RULE,
    "❯ ", RULE, "  orbit · Opus · $19 · busy [PONYTAIL]", "  ⏵⏵ auto mode on", "", ""])
DIALOG = "\n".join([
    "⏺ Bash(rm -rf build)", RULE, " Bash command", "   rm -rf build",
    " Do you want to proceed?", " ❯ 1. Yes", "   2. No", ""])


def t_screen_parse_and_trim():
    """One osascript blob -> per-tty screens -> tile text without the footer."""
    from orbit import sessions as SS
    got = SS.parse_screens("\x02/dev/ttys1\x03a\nb\x02/dev/ttys2\x03c")
    assert got == {"/dev/ttys1": "a\nb", "/dev/ttys2": "c"}, got
    assert SS.trim_footer(SCREEN) == ["⏺ Bash(pytest)", "  14/14 passed", "",
                                      "✳ Concocting… (4m 6s)"], SS.trim_footer(SCREEN)
    # a dialog replaced the input box: nothing is cut, the question stays visible
    assert SS.trim_footer(DIALOG)[-1] == "   2. No"
    # a rule inside earlier output does not fool it: only the LAST two count
    two = "\n".join([RULE, "old output", RULE, "more"]) + "\n" + SCREEN
    assert SS.trim_footer(two)[-1] == "✳ Concocting… (4m 6s)"


def t_reply_guard():
    """Type only into a real input box, never into a session that needs you."""
    from orbit import sessions as SS
    assert SS.can_reply({"state": "busy"}, SCREEN)
    assert SS.can_reply({"state": "idle"}, SCREEN)
    assert not SS.can_reply({"state": "needs_you"}, SCREEN)
    assert not SS.can_reply({"state": "idle"}, DIALOG), "stale pulse, dialog on screen"
    assert not SS.can_reply({"state": "idle"}, ""), "no screen read yet"
    assert jump._q('say "hi" \\ done') == '"say \\"hi\\" \\\\ done"'


def t_ladder_content_gate():
    """Every stage is passable (its reference solution passes) and a real
    step (the previous stage's solution fails it). A learner can't tell a
    broken test from their own bug, so this must never regress."""
    from orbit import ladder as L
    for unit, _ in L.ORDER:
        sol = os.path.join(L.UNITS, unit, ".solutions", "%02d.py")
        prev = "# empty\n"
        for n, md, test in L.stages(unit):
            with open(sol % n) as f:
                code = f.read()
            ok, msg = L.run(code, test, unit)
            assert ok, "%s stage %d solution fails its own test: %s" % (unit, n, msg)
            assert not L.run(prev, test, unit)[0], "%s stage %d is passed by stage %d's code" % (unit, n, n - 1)
            prev = code
        assert len(L.CAN[unit]) == len(L.stages(unit)) == 8, unit
    ok, msg = L.run("while True:\n    pass\n", L.stages("kv")[0][2], "kv", timeout=1)
    assert not ok and "infinite loop" in msg, msg


def t_ladder_progress():
    import datetime
    from orbit import ladder as L
    d = datetime.date(2026, 9, 30)
    p = {}
    assert L.mark_passed(p, "kv", 1, d) == "unaided"
    L.mark_pasted(p, "kv", 2)
    assert L.mark_passed(p, "kv", 2, d) == "pasted"
    assert L.current(p, "kv") == 3
    p["kv"]["pasted"] = []
    L.mark_passed(p, "kv", 2, d)
    assert p["kv"]["passed"]["2"] == "unaided", "an unaided redo upgrades the grade"
    days = ["2026-09-27", "2026-09-28", "2026-09-29"]
    assert L.streak(days, d) == 3, "today not done yet does not break the streak"
    assert L.streak(days + ["2026-09-30"], d) == 4
    assert L.streak(["2026-09-27"], d) == 0


def t_review_leak_guard():
    from orbit import ladder as L
    assert not L.leaks_code("Line 9 crashes. How could you ask whether `key` is there?\nGood.")
    assert L.leaks_code("```python\nx = 1\n```")
    assert L.leaks_code("Try this:\nif key not in db:\nreturn None")


def t_ladder_hints():
    """Level 3 may show a skeleton, never a finished line; level 4 reveals
    exactly the next missing line and grades the stage 'shown'."""
    from orbit import ladder as L
    assert not L.leaks_code("```python\n___ = {}\n```\nPut the name in.", blanks_ok=True)
    assert L.leaks_code('```\ndb = {}\n```', blanks_ok=True), "a finished line is a leak"
    sol = 'db = {}\ndb["name"] = "S"\n'
    assert L.next_missing_line(sol, "# start\n") == (1, "db = {}")
    assert L.next_missing_line(sol, "db = {}\n") == (2, 'db["name"] = "S"')
    assert L.next_missing_line(sol, sol) is None
    assert set(L.HINT_LEVELS) == {1, 2, 3}
    p = {}
    L.unit_state(p, "kv")["shown"].append(1)
    L.mark_pasted(p, "kv", 1)
    assert L.mark_passed(p, "kv", 1) == "shown", "shown outranks pasted"
    for unit, _ in L.ORDER:
        for n, _, _ in L.stages(unit):
            assert os.path.isfile(L.solution_path(unit, n)), (unit, n)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("  ok   %s" % fn.__name__)
        except AssertionError as e:
            failed += 1
            print("  FAIL %s: %s" % (fn.__name__, e))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
