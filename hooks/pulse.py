#!/usr/bin/env python3
"""pulse — one small JSON per live Claude Code session, kept fresh by hooks.

Runs (async) on SessionStart · UserPromptSubmit · PostToolUse · PostToolUseFailure ·
Notification · Stop · StopFailure · SubagentStop · PreCompact · SessionEnd and writes
~/.config/orbit/pulse/<session_id>.json. orbit's sessions tab reads those files;
nothing ever polls a transcript. install.sh prints the settings.json lines.

Stdlib only, runs under macOS's own /usr/bin/python3 (3.9).
Every step is O(1): the transcript is tailed (last 64 KB), never parsed whole.

    /usr/bin/python3 hooks/pulse.py --selftest
"""
import glob, json, os, sys, time

HOME = os.path.expanduser("~")
PULSE = os.path.join(HOME, ".config/orbit/pulse")
LIVE = os.path.join(HOME, ".claude/sessions")

STATE = {  # hook_event_name -> state. Notification is decided by notification_type.
    "SessionStart": "idle", "UserPromptSubmit": "busy", "PostToolUse": "busy",
    "PreCompact": "busy", "Stop": "idle", "SubagentStop": "busy",
    "PostToolUseFailure": "error", "StopFailure": "error", "SessionEnd": "ended",
}
# idle_prompt is NOT here: it fires ~60s after a Stop, so it means "finished a while ago".
NEEDS_YOU = {"permission_prompt", "agent_needs_input", "elicitation_dialog"}


def tail_facts(path, nbytes=65536):
    """Newest ai-title / away_summary from the END of the transcript: the tile
    title, and the recap a side-project card offers as its next action."""
    out = {}
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - nbytes))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return out
    for line in reversed(lines):
        if len(out) >= 2:
            break
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = d.get("type")
        if t == "ai-title" and "title" not in out:
            out["title"] = d.get("aiTitle", "")
        elif t == "system" and d.get("subtype") == "away_summary" and "summary" not in out:
            out["summary"] = (d.get("content") or d.get("message") or "")[:200]
    return out


def live_pids():
    """session_id -> pid for every Claude CLI that is actually alive right now."""
    alive = {}
    for f in glob.glob(os.path.join(LIVE, "*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
            os.kill(int(d["pid"]), 0)
            alive[d["sessionId"]] = d
        except (OSError, ValueError, KeyError, ProcessLookupError):
            continue
    return alive


def reconcile(now):
    """Age out sessions whose process is gone; drop ended ones after a day."""
    alive = live_pids()
    for f in glob.glob(os.path.join(PULSE, "*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        sid = d.get("session_id")
        if d.get("state") == "ended":
            if now - d.get("last_event_at", now) > 86400:
                os.unlink(f)
            continue
        if sid not in alive and now - d.get("last_event_at", now) > 600:
            d["state"] = "ended"
            write(d)


def write(d):
    tmp = os.path.join(PULSE, ".%s.tmp" % d["session_id"])
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, os.path.join(PULSE, d["session_id"] + ".json"))


def handle(ev, now=None):
    now = now or time.time()
    sid = ev.get("session_id")
    if not sid:
        return None
    path = os.path.join(PULSE, sid + ".json")
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {"session_id": sid, "started_at": int(now), "error_count": 0}
    name = ev.get("hook_event_name", "")
    cwd = ev.get("cwd") or d.get("cwd") or HOME
    d["cwd"] = cwd
    d["project"] = os.path.basename(cwd.rstrip("/")) if cwd != HOME else "home"
    d["last_event"] = name
    d["last_event_at"] = int(now)
    if name == "Notification":
        d["state"] = "needs_you" if ev.get("notification_type") in NEEDS_YOU else d.get("state", "idle")
    else:
        d["state"] = STATE.get(name, d.get("state", "idle"))
    # waiting_since: when this session started waiting on the user. Set on entering
    # needs_you or on Stop (= finished), kept through later idle_prompts, cleared once
    # Claude is working again. Orbit's inbox sorts by it.
    if d["state"] == "needs_you" or name == "Stop":
        d.setdefault("waiting_since", int(now))
    elif d["state"] != "idle" or name == "SessionStart":
        d.pop("waiting_since", None)
    if name in ("PostToolUse", "PostToolUseFailure"):
        d["last_tool"] = ev.get("tool_name", "")
    if name == "PostToolUseFailure":
        d["error_count"] = d.get("error_count", 0) + 1
    if name == "StopFailure":
        d["error_count"] = d.get("error_count", 0) + 1
        d["last_error"] = ev.get("error_type", "")
    live = live_pids().get(sid)
    if live:
        d["pid"] = live.get("pid")
        d["name"] = live.get("name", "")
    tp = ev.get("transcript_path")
    if tp and os.path.isfile(tp):
        d["transcript"] = tp  # orbit reads Claude Code's file-history snapshots from it
        d.update(tail_facts(tp))
    write(d)
    return d


def selftest():
    import tempfile
    global PULSE, LIVE
    tmp = tempfile.mkdtemp()
    PULSE, LIVE = os.path.join(tmp, "pulse"), os.path.join(tmp, "live")
    os.makedirs(PULSE); os.makedirs(LIVE)
    tr = os.path.join(tmp, "t.jsonl")
    with open(tr, "w") as f:
        f.write(json.dumps({"type": "ai-title", "aiTitle": "Old"}) + "\n")
        f.write(json.dumps({"type": "system", "subtype": "away_summary", "content": "Tests pass."}) + "\n")
        f.write(json.dumps({"type": "ai-title", "aiTitle": "Living desktop"}) + "\n")
    proj = os.path.join(tmp, "proj"); os.makedirs(proj)
    with open(os.path.join(LIVE, "1.json"), "w") as f:
        json.dump({"pid": os.getpid(), "sessionId": "s1", "name": "test"}, f)
    base = {"session_id": "s1", "cwd": proj, "transcript_path": tr}
    d = handle(dict(base, hook_event_name="SessionStart"))
    assert d["state"] == "idle" and "waiting_since" not in d and d["title"] == "Living desktop", d
    assert d["summary"] == "Tests pass.", d
    assert d["project"] == "proj" and d["pid"] == os.getpid(), d
    assert handle(dict(base, hook_event_name="UserPromptSubmit"))["state"] == "busy"
    d = handle(dict(base, hook_event_name="PostToolUseFailure", tool_name="Bash"))
    assert d["state"] == "error" and d["error_count"] == 1 and d["last_tool"] == "Bash"
    assert handle(dict(base, hook_event_name="Notification", notification_type="auth_success"))["state"] == "error"
    assert handle(dict(base, hook_event_name="Notification", notification_type="permission_prompt"))["state"] == "needs_you"
    handle(dict(base, hook_event_name="UserPromptSubmit"))  # user answered; Claude works again
    d = handle(dict(base, hook_event_name="Stop"), now=1000)
    assert d["state"] == "idle" and d["waiting_since"] == 1000, d
    d = handle(dict(base, hook_event_name="Notification", notification_type="idle_prompt"), now=1060)
    assert d["state"] == "idle" and d["waiting_since"] == 1000, d  # still finished, same wait start
    assert "waiting_since" not in handle(dict(base, hook_event_name="UserPromptSubmit"))
    assert handle(dict(base, hook_event_name="Stop"))["state"] == "idle"
    assert handle(dict(base, hook_event_name="SessionEnd"))["state"] == "ended"
    # reconcile: a dead pid ages out, an ended file older than a day is removed
    handle({"session_id": "s2", "cwd": proj, "hook_event_name": "SessionStart"}, now=time.time() - 700)
    reconcile(time.time())
    with open(os.path.join(PULSE, "s2.json")) as f:
        assert json.load(f)["state"] == "ended"
    handle(dict(base, hook_event_name="SessionEnd"), now=time.time() - 90000)
    reconcile(time.time())
    assert not os.path.exists(os.path.join(PULSE, "s1.json"))
    print("pulse selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    os.makedirs(PULSE, exist_ok=True)
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)
    try:
        handle(ev)
        reconcile(time.time())
    except Exception:
        pass  # a hook must never break a session
