"""Live Claude sessions on this Mac, read from pulse files.

hooks/pulse.py keeps one JSON per session in ~/.config/orbit/pulse/.
This module reads them, drops what is dead or has no window, orders the
inbox, and diffs what Claude changed. The diff needs no hook of its own:
Claude Code already backs up every file before its first edit (for /rewind)
under ~/.claude/file-history/<session>/. Ceiling: only Edit/Write-tool edits
are seen; a file Claude changes through Bash (sed, a script) is invisible.
Stdlib only.
"""

import difflib
import glob
import hashlib
import json
import os
import subprocess

HOME = os.path.expanduser("~")
PULSE = os.path.join(HOME, ".config/orbit/pulse")
HISTORY = os.path.join(HOME, ".claude/file-history")

RANK = {"needs_you": 0, "finished": 1}
_TTY = {}                 # pid -> tty; a live pid never changes terminal


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def tty(pid):
    """'/dev/ttys011', or None for a headless claude (Agent SDK, claude -p)."""
    if pid not in _TTY:
        out = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)],
                             stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
        _TTY[pid] = "/dev/" + out if out and out != "??" else None
    return _TTY[pid]


def load():
    """Sessions you could jump to right now. Pulse's own stale check only runs
    when some hook fires, so a crashed session is judged here, by its pid."""
    rows = []
    for f in glob.glob(os.path.join(PULSE, "*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        if d.get("state") == "ended" or not alive(d.get("pid")):
            continue
        d["tty"] = tty(d["pid"])
        if d["tty"]:
            rows.append(d)
    return rows


def kind(d):
    """needs_you / finished / None. A fresh session is idle but not finished:
    pulse only sets waiting_since on Stop or on a real needs-you."""
    if d.get("state") == "needs_you":
        return "needs_you"
    if d.get("state") == "idle" and d.get("waiting_since"):
        return "finished"
    return None


def inbox(rows):
    """Needs-you first, then finished; longest wait first within each."""
    waiting = [r for r in rows if kind(r)]
    return sorted(waiting, key=lambda r: (RANK[kind(r)], r["waiting_since"]))


EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def changed_files(transcript):
    """Absolute paths Claude edited in this session, in first-edit order.
    Read from its tool calls: the transcript's own file-history snapshots are
    written late and sometimes skip v1, so they cannot be the list."""
    seen = []
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"tool_use"' not in line:
                    continue
                try:
                    content = json.loads(line)["message"]["content"]
                except (ValueError, KeyError, TypeError):
                    continue
                for c in content if isinstance(content, list) else []:
                    if c.get("type") == "tool_use" and c.get("name") in EDIT_TOOLS:
                        inp = c.get("input") or {}
                        p = inp.get("file_path") or inp.get("notebook_path")
                        if p and p not in seen:
                            seen.append(p)
    except OSError:
        pass
    return seen


def backup_of(sid, path):
    """Claude Code's copy of `path` from just before its first edit, or None
    if the file did not exist yet. Named sha256(path)[:16]@v1, written the
    moment the edit happens (verified 2026-09-29)."""
    b = os.path.join(HISTORY, sid,
                     hashlib.sha256(path.encode("utf-8")).hexdigest()[:16] + "@v1")
    return b if os.path.isfile(b) else None


def diff(sid, path):
    """Unified diff from before Claude's first edit to the file as it is now.
    Includes your own edits since then: there is no way to tell them apart."""
    before, after = [], []
    b = backup_of(sid, path)
    for src, dst in ((b, before), (path, after)):
        if src:
            try:
                with open(src, errors="replace") as f:
                    dst.extend(f.read().splitlines(True))
            except OSError:
                pass                                # deleted since
    return "".join(difflib.unified_diff(
        before, after, "before Claude" if b else "(new file)", "now"))


# ---------------------------------------------------------- tile screens
# Terminal.app hands orbit the visible text of each tab (jump.screens). These
# pure helpers turn one Claude Code screen into a tile and decide whether a
# reply may be typed into it.

def parse_screens(out):
    """'\x02<tty>\x03<text>' repeated -> {tty: text}. Not \x1e/\x1f: Python's
    strip() counts those as whitespace and eats the first separator."""
    screens = {}
    for part in out.split("\x02")[1:]:
        tty, _, text = part.partition("\x03")
        screens[tty] = text
    return screens


def _rules(lines):
    """Indexes of Claude Code's full-width ──── lines, which frame its input box."""
    return [i for i, l in enumerate(lines)
            if len(l.strip()) > 10 and set(l.strip()) <= {"─"}]


def trim_footer(text):
    """Screen minus the input box, statusline and mode line: cut at the upper
    of the last two rules. No rule pair (a permission dialog or picker has
    replaced the box) -> keep everything; showing too much beats hiding."""
    lines = text.rstrip("\n").split("\n")
    r = _rules(lines)
    if len(r) >= 2:
        lines = lines[:r[-2]]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def has_input_box(text):
    """A ❯ prompt line between the last two rules = Claude's normal input box.
    It is there while Claude works too, so it says 'typing is safe', never 'idle'."""
    lines = text.rstrip("\n").split("\n")
    r = _rules(lines)
    return len(r) >= 2 and any(l.lstrip().startswith("❯") for l in lines[r[-2] + 1:r[-1]])


def can_reply(d, text):
    """Only into a real input box, never into a session that needs you: text
    typed into a permission menu could pick an option. The screen can only make
    this stricter than pulse, never looser."""
    return d.get("state") != "needs_you" and has_input_box(text or "")
