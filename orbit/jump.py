"""Jump-outs: claude, shell, copy, reveal -- local and remote.

The whole file exists because of one fact: `ssh other-mac <cmd>` runs with
PATH=/usr/bin:/bin:/usr/sbin:/sbin, where neither `tmux` (/opt/homebrew/bin)
nor `claude` (~/.local/bin) exists. Every remote command must go through a
login shell.
"""

import os
import shlex
import subprocess

from . import config as C

HOME = os.path.expanduser("~")


def abs_dir(host, repo_path, sub=""):
    """The directory for a node at any depth. Absolute on this Mac; on
    another Mac it stays ~/-relative, because only its own shell knows its
    home (see sh_path)."""
    base = HOME if host == C.LOCAL else "~"
    parts = [base.rstrip("/"), (repo_path or "").strip("/")]
    if sub:
        parts.append(sub.strip("/"))
    return "/".join(p for p in parts if p)


def sh_path(path):
    """A path quoted for a shell, with a leading ~ left for that shell to
    expand: shlex.quote alone would turn it into a literal '~' folder."""
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        return '"$HOME"/' + shlex.quote(path[2:])
    return shlex.quote(path)


def remote_cmd(host, path, inner):
    """The ssh argv for running `inner` in `path` on another Mac.

    Quoted twice on purpose: once so the path survives (`~/my project`),
    once so the whole `zsh -lc` argument survives ssh's own shell.
    """
    cd = "cd %s && %s" % (sh_path(path), inner)
    return ["ssh", "-t", C.HOSTS.get(host, host), "zsh -lc " + shlex.quote(cd)]


def claude(host, repo_path, sub=""):
    d = abs_dir(host, repo_path, sub)
    if host != C.LOCAL:
        return remote_cmd(host, d, "exec claude")
    return ["claude"], d


def shell(host, repo_path, sub="", session=None):
    d = abs_dir(host, repo_path, sub)
    sess = session or ("orbit-" + os.path.basename(repo_path or "home"))
    tmux = "tmux new-session -A -s %s -c %s" % (shlex.quote(sess), sh_path(d))
    if host != C.LOCAL:
        return remote_cmd(host, d, "exec " + tmux)
    return shlex.split(tmux), d


def run(spec):
    """Execute whatever claude()/shell()/start() returned."""
    if isinstance(spec, tuple):
        argv, cwd = spec
        return subprocess.call(argv, cwd=cwd)
    return subprocess.call(spec)


def _osa(script, timeout=5):
    """'' on failure or a hung Terminal: callers run this on worker threads."""
    try:
        return subprocess.run(["osascript", "-e", script], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=timeout).stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


def _q(s):
    """An AppleScript string literal."""
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def focus_tty(tty):
    """Bring the Terminal.app tab on this tty to the front. False if no tab has
    it. The first call triggers macOS's one-time Automation prompt."""
    return _osa("""tell application "Terminal"
  repeat with w in windows
    repeat with t in tabs of w
      if tty of t is %s then
        set selected of t to true
        set index of w to 1
        activate
        return "ok"
      end if
    end repeat
  end repeat
end tell""" % _q(tty)) == "ok"


def frontmost_tty():
    """tty of the Terminal tab you are looking at, or '' if Terminal is not in front."""
    return _osa("""tell application "System Events" to set p to name of first process whose frontmost is true
if p is "Terminal" then tell application "Terminal" to return tty of selected tab of front window
return \"\"""")


def claude_window(d, seed="", background=False):
    """Local claude in a NEW Terminal window. Running it inside orbit's own
    terminal would freeze orbit (no inbox, no ping) and give the session
    orbit's tty, so jumping to it would land back on orbit. background=True
    skips `activate`; the caller puts orbit's own tab back in front."""
    cmd = "cd %s && claude" % shlex.quote(d) + (" " + shlex.quote(seed) if seed else "")
    _osa('tell application "Terminal"\n  do script %s%s\nend tell'
         % (_q(cmd), "" if background else "\n  activate"))


def screens(ttys):
    """Visible text of the Terminal tabs on these ttys, in ONE osascript call
    (~0.7 s for 14 windows). Tabs are addressed by index: a `repeat with t in`
    loop variable is a reference, and `contents of t` dereferences it instead
    of reading the tab. Parse with sessions.parse_screens."""
    if not ttys:
        return ""
    return _osa("""set out to ""
set want to {%s}
tell application "Terminal"
  repeat with w from 1 to count windows
    repeat with i from 1 to count tabs of window w
      set k to tty of tab i of window w
      if want contains k then set out to out & (character id 2) & k & (character id 3) & (contents of tab i of window w)
    end repeat
  end repeat
end tell
return out""" % ", ".join(_q(t) for t in ttys))


def send(tty, line):
    """Type one line + Return into the Terminal tab on `tty`. Newlines would
    submit early and escapes would drive the TUI, so both are stripped."""
    line = "".join(ch for ch in line if ch >= " " and ch != "\x7f").strip()
    if not line:
        return False
    return _osa("""tell application "Terminal"
  repeat with w from 1 to count windows
    repeat with i from 1 to count tabs of window w
      if tty of tab i of window w is %s then
        do script %s in tab i of window w
        return "ok"
      end if
    end repeat
  end repeat
end tell""" % (_q(tty), _q(line))) == "ok"


def ping():
    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def copy_path(text):
    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    p.communicate(text.encode("utf-8"))


def remote_path(host, d):
    """'mini:~/repo' style, the form scp and rsync accept."""
    return "%s:%s" % (C.HOSTS.get(host, host), d)


def reveal(host, repo_path, sub=""):
    """Finder only knows about this machine; remote paths get copied instead."""
    d = abs_dir(host, repo_path, sub)
    if host != C.LOCAL:
        copy_path(remote_path(host, d))
        return False
    subprocess.call(["open", "-R", d])
    return True
