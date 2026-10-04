"""orbit refresh -- the daemon body. Scan every host, merge, pull bodies.

Zero third-party imports on purpose: a broken `pip install` can take out the
viewer but must never take out the index.
"""

import fcntl
import gzip
import json
import os
import shlex
import subprocess
import sys
import tarfile
import threading
import time

from . import config as C
from . import db as D
from . import scan as S

HOME = os.path.expanduser("~")
TAGS = os.path.join(HOME, ".config/orbit/tags.json")
LOCK = os.path.expanduser("~/.local/share/orbit/refresh.lock")
SCAN_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan.py")

GH_EVERY = 6 * 3600          # seconds; gh needs the network, so it lags


# ----------------------------------------------------------------- themes

def load_tags():
    try:
        with open(TAGS) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_tags(tags):
    os.makedirs(os.path.dirname(TAGS), exist_ok=True)
    tmp = TAGS + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(tags, fh, indent=2, sort_keys=True)
    os.replace(tmp, TAGS)


def theme_for(host, path, name, remote, tags, themes=None, mine=None):
    """Resolution order, highest wins: explicit tag, foreign remote owner,
    name prefix, else UNTAGGED. themes/mine default to config.json."""
    themes = C.THEMES if themes is None else themes
    mine = C.MINE if mine is None else mine
    for k in (host + ":" + path, host + ":" + name, path, name):
        if k in tags:
            return tags[k]

    # Remote owner outranks name guessing: someone else's clone named like
    # one of your themes is third-party no matter what the name suggests.
    # With no owners configured nothing is third-party: we cannot tell.
    if mine and remote:
        owner = remote.rstrip("/").replace(":", "/").split("/")[-2:]
        owner = owner[0] if len(owner) == 2 else ""
        if owner and owner.lower() not in {m.lower() for m in mine}:
            return "THIRD-PARTY"

    low = name.lower()
    for theme, prefixes in themes.items():
        for pre in prefixes:
            if low.startswith(pre.lower()):
                return theme
    return "UNTAGGED"


def meta_factory(host, tags):
    def meta_for(path, name, remote):
        return {"theme": theme_for(host, path, name, remote, tags)}
    return meta_for


# ----------------------------------------------------------------- scan

def scan_local():
    S.IGNORE_PATHS = tuple(p.strip("/") for p in C.IGNORE)
    return S.scan(HOME, C.EXTRA_ROOTS)


def scan_remote(ssh_host, timeout=120):
    """One ssh call: the scanner source goes in on stdin, gzipped JSON comes
    back on stdout. Nothing is ever installed on the other Mac."""
    with open(SCAN_PY, "rb") as fh:
        src = fh.read()
    args = list(C.EXTRA_ROOTS) + ["!" + p for p in C.IGNORE]
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
           ssh_host, "/usr/bin/python3", "-"] + [shlex.quote(a) for a in args]
    p = subprocess.run(cmd, input=src, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or b"").decode()[:400] or
                           "ssh exit %d" % p.returncode)
    return json.loads(gzip.decompress(p.stdout))


# ----------------------------------------------------------------- bodies

def pending_bodies(db, host, limit=None):
    sql = ("SELECT f.id, r.path AS repo_path, f.path, f.size, f.mtime "
           "FROM file f JOIN repo r ON r.id=f.repo_id "
           "WHERE r.host=? AND f.size<=? "
           "  AND (f.body_mtime IS NULL OR f.body_mtime < f.mtime) "
           "ORDER BY f.mtime DESC")
    if limit:
        sql += " LIMIT %d" % int(limit)
    rows = db.execute(sql, (host, S.MAX_BODY)).fetchall()
    return [r for r in rows if S.is_text(r["path"].rsplit("/", 1)[-1])]


def store_body(db, file_id, raw, mtime):
    """Record the attempt either way: a file that is binary despite a text
    extension must not be re-fetched every cycle for the rest of time."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is None or "\x00" in text[:4096]:
        db.execute("UPDATE file SET body_mtime=? WHERE id=?", (mtime, file_id))
        return False
    db.execute("DELETE FROM body WHERE rowid=?", (file_id,))
    db.execute("INSERT INTO body(rowid,text) VALUES(?,?)", (file_id, text))
    db.execute("UPDATE file SET body_mtime=? WHERE id=?", (mtime, file_id))
    return True


def pull_local(db, rows):
    n = 0
    for r in rows:
        p = os.path.join(HOME, r["repo_path"], r["path"])
        try:
            with open(p, "rb") as fh:
                raw = fh.read(S.MAX_BODY + 1)
        except OSError:
            continue
        if store_body(db, r["id"], raw, r["mtime"]):
            n += 1
    return n


def chunks(rows, max_files=2000, max_bytes=24 * 1024 * 1024):
    """Batch by count AND bytes: a batch of large files must not become one
    enormous tar stream."""
    batch, size = [], 0
    for r in rows:
        if batch and (len(batch) >= max_files or size + r["size"] > max_bytes):
            yield batch
            batch, size = [], 0
        batch.append(r)
        size += r["size"]
    if batch:
        yield batch


def pull_remote(db, ssh_host, rows):
    """One `tar czf -` per chunk, NUL-separated file list on stdin, streamed
    straight into FTS5. NUL separation is what makes 'my project' survive.

    --no-recursion is load-bearing: without it, any listed path that turns out
    to be a directory makes tar stream the whole subtree, and in streaming mode
    tarfile must decompress past every unwanted member. One such path cost 45s.
    """
    n = 0
    for i, batch in enumerate(chunks(rows)):
        by_path = {}
        for r in batch:
            by_path[r["repo_path"] + "/" + r["path"]] = r
        # no trailing NUL: bsdtar reads a final empty entry as "" and tries to
        # stat the whole -C directory
        payload = b"\0".join(k.encode("utf-8") for k in by_path)

        # "$HOME" is expanded by the remote shell: its home is never configured
        p = subprocess.Popen(
            ["ssh", "-o", "BatchMode=yes", ssh_host,
             'tar czf - --no-recursion -C "$HOME" --null -T -'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL)

        def feed():
            try:
                p.stdin.write(payload)
                p.stdin.close()
            except OSError:
                pass
        t = threading.Thread(target=feed)
        t.start()

        t_read = t_write = 0.0
        seen = set()
        try:
            with tarfile.open(fileobj=p.stdout, mode="r|gz") as tf:
                for m in tf:
                    if not m.isfile():
                        continue
                    r = by_path.get(m.name)
                    if r is None:
                        continue
                    _t = time.time()
                    f = tf.extractfile(m)
                    raw = f.read() if f is not None else None
                    t_read += time.time() - _t
                    if raw is None:
                        continue
                    _t = time.time()
                    ok = store_body(db, r["id"], raw, r["mtime"])
                    t_write += time.time() - _t
                    seen.add(m.name)
                    if ok:
                        n += 1
        except tarfile.TarError:
            pass
        finally:
            t.join()
            p.stdout.close()
            p.wait()
        # Anything tar could not produce -- deleted since the scan, or
        # unreadable -- is marked attempted so it stops being requested forever.
        missing = [(r["mtime"], r["id"]) for k, r in by_path.items()
                   if k not in seen]
        if missing:
            db.executemany("UPDATE file SET body_mtime=? WHERE id=?", missing)
        _t = time.time()
        db.commit()
        if os.environ.get("ORBIT_TRACE"):
            print("   chunk %d: read %.1fs  fts5 %.1fs  commit %.1fs"
                  % (i, t_read, t_write, time.time() - _t))
    return n


# --------------------------------------------------------------- github

def refresh_gh(db):
    p = subprocess.run(
        ["gh", "repo", "list", "--limit", "300", "--json",
         "name,owner,visibility,pushedAt,description,url"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or b"").decode()[:200])
    rows = json.loads(p.stdout)
    db.execute("DELETE FROM gh")
    db.executemany(
        "INSERT INTO gh(nwo,name,private,pushed_at,description,url) "
        "VALUES(?,?,?,?,?,?)",
        [(r["owner"]["login"] + "/" + r["name"], r["name"],
          1 if r["visibility"] == "PRIVATE" else 0,
          r.get("pushedAt"), r.get("description"), r.get("url"))
         for r in rows])
    D.set_meta(db, "gh_as_of", int(time.time()))
    return len(rows)


# ----------------------------------------------------------------- main

def run(bodies=True, gh=True, verbose=False):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("skipped: already running")
        return 0

    t0 = time.time()
    db = D.connect()
    tags = load_tags()
    parts = []
    scanned = []

    for host in C.ALL_HOSTS:
        ts = time.time()
        try:
            doc = scan_local() if host == C.LOCAL else scan_remote(C.HOSTS[host])
        except Exception as e:                       # noqa: BLE001
            D.set_meta(db, host + "_error", str(e)[:300])
            parts.append("%s=ERR" % host)
            if verbose:
                print("%s scan failed: %s" % (host, e), file=sys.stderr)
            continue
        D.set_meta(db, host + "_error", "")
        scanned.append(host)
        t_scan = time.time() - ts
        ts = time.time()
        nr, new, ch, gone = D.merge_host(
            db, host, doc, meta_factory(host, tags))
        db.commit()
        parts.append("%s=%dr/%df(+%d~%d-%d scan%.1f merge%.1f)"
                     % (host, nr, sum(len(r["files"]) for r in doc["repos"]),
                        new, ch, gone, t_scan, time.time() - ts))

    if bodies:
        nb, timings = 0, []
        # only hosts that answered this cycle: an unreachable host would make
        # every pending file look deleted and mark it as attempted
        for host in scanned:
            ts = time.time()
            rows = pending_bodies(db, host)
            if host == C.LOCAL:
                nb += pull_local(db, rows)
            elif rows:
                nb += pull_remote(db, C.HOSTS[host], rows)
            db.commit()
            timings.append("%s=%.1fs[%d]" % (host, time.time() - ts, len(rows)))
        parts.append("bodies+%d(%s)" % (nb, " ".join(timings)))

    if gh and C.GITHUB:
        last = int(D.get_meta(db, "gh_as_of", 0) or 0)
        if time.time() - last > GH_EVERY:
            try:
                n = refresh_gh(db)
                parts.append("gh=%d" % n)
            except Exception as e:                   # noqa: BLE001
                D.set_meta(db, "gh_error", str(e)[:200])
                parts.append("gh=ERR")

    D.set_meta(db, "last_run_ms", int((time.time() - t0) * 1000))
    db.commit()
    line = "%s ok %s %.1fs" % (time.strftime("%Y-%m-%dT%H:%M"),
                               " ".join(parts), time.time() - t0)
    print(line)
    db.close()
    return 0
