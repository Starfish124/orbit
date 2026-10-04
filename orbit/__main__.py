"""orbit CLI. Bare `orbit` launches the TUI; every subcommand works headless."""

import argparse
import json
import os
import sys
import time

from . import config as C
from . import db as D


def ago(ts):
    if not ts:
        return "never"
    d = int(time.time()) - int(ts)
    if d < 90:
        return "%ds" % d
    if d < 5400:
        return "%dm" % (d // 60)
    if d < 172800:
        return "%dh" % (d // 3600)
    return "%dd" % (d // 86400)


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def one_repo(db, ref):
    rows = D.resolve_repo(db, ref)
    if not rows:
        die("no repo matching %r  (try: orbit repos)" % ref)
    if len(rows) > 1 and rows[0]["name"] != ref:
        names = ", ".join("%s:%s" % (r["host"], r["path"]) for r in rows[:8])
        die("ambiguous %r -> %s" % (ref, names))
    return rows[0]


# ------------------------------------------------------------- commands

def cmd_repos(db, a):
    rows = D.repos(db, theme=a.theme, host=a.host, flat=a.flat)
    if a.stale:
        rows = [r for r in rows if not r["remote"]]
    if a.json:
        print(json.dumps([dict(r) for r in rows], indent=2))
        return
    theme = None
    for r in rows:
        if not a.flat and r["theme"] != theme:
            theme = r["theme"]
            print("\n%s" % theme)
        mark = " " if r["remote"] else "*"
        print("  %-34s %-9s %-16s %6d files  %7.1f MB  %s%s"
              % (r["name"][:34], r["host"], (r["branch"] or "-")[:16],
                 r["n_files"], r["n_bytes"] / 1e6, ago(r["mtime"]), mark))
    if not a.flat and rows:
        print("\n%d repos   * = no remote" % len(rows))


def cmd_tree(db, a):
    r = one_repo(db, a.repo)
    prefix = (a.subpath.strip("/") + "/") if a.subpath else ""

    def walk(pref, depth, indent):
        if depth > a.depth:
            return
        dirs, files = D.children(db, r["id"], pref)
        for d in dirs:
            print("%s%s/" % (indent, d))
            walk(pref + d + "/", depth + 1, indent + "  ")
        for f in files:
            flag = "" if f["body_mtime"] else "  (no body)"
            print("%s%s%s" % (indent, f["path"][len(pref):], flag))

    print("%s:%s   %s" % (r["host"], r["path"], r["theme"]))
    walk(prefix, 1, "  ")


def cmd_find(db, a):
    repo_id = one_repo(db, a.repo)["id"] if a.repo else None
    out = []
    if not a.content:
        for r in D.find_names(db, a.query, a.host, repo_id, a.limit):
            out.append({"host": r["host"], "repo": r["repo"],
                        "path": r["path"], "kind": "name"})
    if not a.names:
        try:
            for r in D.find_content(db, a.query, a.host, repo_id, a.limit):
                out.append({"host": r["host"], "repo": r["repo"],
                            "path": r["path"], "kind": "content",
                            "snippet": " ".join(r["snip"].split())})
        except Exception as e:                       # bad FTS5 syntax
            if a.names is False and not out:
                die("search failed: %s" % e)
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        for r in out:
            line = "%-8s %s/%s" % (r["host"], r["repo"], r["path"])
            if r.get("snippet"):
                line += "\n         " + r["snippet"][:160]
            print(line)
    sys.exit(0 if out else 1)


def cmd_cat(db, a):
    ref, _, rel = a.target.partition("/")
    if not rel:
        die("usage: orbit cat <repo>/<path>")
    r = one_repo(db, ref)
    row = db.execute("SELECT id,body_mtime FROM file WHERE repo_id=? AND path=?",
                     (r["id"], rel)).fetchone()
    if not row:
        die("no such file in index: %s/%s" % (r["name"], rel))
    text = D.body_of(db, row["id"])
    if text is None:
        die("no body indexed (binary, too large, or not pulled yet)")
    sys.stdout.write(text)


def cmd_gaps(db, a):
    missing, never = D.gaps(db)

    print("ON GITHUB, NOT CLONED  (%d)" % len(missing))
    for g in missing:
        print("  %-38s %-8s %s" % (g["name"][:38],
                                   "private" if g["private"] else "public",
                                   (g["pushed_at"] or "")[:10]))
    print("\nLOCAL, NEVER PUSHED  (%d)" % len(never))
    for r in never:
        print("  %-38s %-9s %s" % (r["name"][:38], r["host"], ago(r["mtime"])))


def cmd_status(db, a):
    c = D.counts(db)
    print("orbit   %d repos · %d files · %d bodies"
          % (c["repos"], c["files"], c["bodies"]))
    for host in C.ALL_HOSTS:
        err = D.get_meta(db, host + "_error", "")
        n = db.execute("SELECT COUNT(*) c FROM repo WHERE host=?",
                       (host,)).fetchone()["c"]
        print("  %-9s %-7s %2d repos%s"
              % (host, ago(D.get_meta(db, host + "_as_of")), n,
                 ("   ERROR: " + err) if err else ""))
    print("  %-9s %-7s %s rows" % ("github", ago(D.get_meta(db, "gh_as_of")),
                                   db.execute("SELECT COUNT(*) c FROM gh")
                                   .fetchone()["c"]))
    try:
        mb = os.path.getsize(D.DB_PATH) / 1e6
        print("  db        %.0f MB   last run %sms"
              % (mb, D.get_meta(db, "last_run_ms", "?")))
    except OSError:
        pass


def cmd_tag(db, a):
    from .refresh import load_tags, save_tags
    themes = list(C.THEMES) + list(C.BUILTIN)
    if a.theme not in themes:
        die("theme must be one of: %s  (add more under \"themes\" in %s)"
            % (", ".join(themes), C.PATH))
    r = one_repo(db, a.repo)
    tags = load_tags()
    tags[r["host"] + ":" + r["path"]] = a.theme
    save_tags(tags)
    db.execute("UPDATE repo SET theme=? WHERE id=?", (a.theme, r["id"]))
    db.commit()
    print("%s:%s -> %s" % (r["host"], r["path"], a.theme))


def cmd_refresh(db, a):
    from . import refresh
    db.close()
    sys.exit(refresh.run(bodies=not a.no_bodies, gh=not a.no_gh, verbose=True))


# ------------------------------------------------------------------ main

def build_parser():
    p = argparse.ArgumentParser(prog="orbit",
                                description="cross-machine project index")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("repos", help="list every indexed repo")
    r.add_argument("--theme"); r.add_argument("--host")
    r.add_argument("--flat", action="store_true",
                   help="pure last-touched order, no theme groups")
    r.add_argument("--stale", action="store_true", help="only repos with no remote")
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_repos)

    t = sub.add_parser("tree", help="file tree of one repo")
    t.add_argument("repo"); t.add_argument("subpath", nargs="?")
    t.add_argument("-d", "--depth", type=int, default=3)
    t.set_defaults(fn=cmd_tree)

    f = sub.add_parser("find", help="search names and contents")
    f.add_argument("query")
    f.add_argument("-n", "--names", action="store_true", help="names only")
    f.add_argument("-c", "--content", action="store_true", help="contents only")
    f.add_argument("--repo"); f.add_argument("--host")
    f.add_argument("--limit", type=int, default=40)
    f.add_argument("--json", action="store_true")
    f.set_defaults(fn=cmd_find)

    c = sub.add_parser("cat", help="print an indexed file, offline")
    c.add_argument("target", metavar="repo/path")
    c.set_defaults(fn=cmd_cat)

    sub.add_parser("gaps", help="GitHub-only and never-pushed repos"
                   ).set_defaults(fn=cmd_gaps)
    sub.add_parser("status", help="freshness and counts").set_defaults(fn=cmd_status)

    g = sub.add_parser("tag", help="set a repo's theme")
    g.add_argument("repo"); g.add_argument("theme")
    g.set_defaults(fn=cmd_tag)

    rf = sub.add_parser("refresh", help="one index cycle (what launchd runs)")
    rf.add_argument("--no-bodies", action="store_true")
    rf.add_argument("--no-gh", action="store_true")
    rf.set_defaults(fn=cmd_refresh)
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from .tui import run_tui
        return run_tui()
    a = build_parser().parse_args(argv)
    if not getattr(a, "fn", None):
        build_parser().print_help()
        return 0
    db = D.connect()
    try:
        a.fn(db, a)
    finally:
        try:
            db.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
