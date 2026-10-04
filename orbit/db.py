"""orbit index -- schema and every query. All SQL lives in this file."""

import os
import sqlite3
import time

DB_PATH = os.path.expanduser("~/.local/share/orbit/index.db")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS repo(
  id          INTEGER PRIMARY KEY,
  host        TEXT NOT NULL,          -- a label from config.json, e.g. 'laptop'
  path        TEXT NOT NULL,          -- home-relative, e.g. 'code/my-app'
  name        TEXT NOT NULL,
  theme       TEXT NOT NULL DEFAULT 'UNTAGGED',
  remote      TEXT,                   -- origin URL; NULL = never pushed
  branch      TEXT,
  last_commit INTEGER,
  mtime       INTEGER NOT NULL DEFAULT 0,   -- newest file inside; drives sorting
  n_files     INTEGER NOT NULL DEFAULT 0,
  n_bytes     INTEGER NOT NULL DEFAULT 0,
  UNIQUE(host, path)
);

CREATE TABLE IF NOT EXISTS file(
  id         INTEGER PRIMARY KEY,
  repo_id    INTEGER NOT NULL REFERENCES repo(id) ON DELETE CASCADE,
  path       TEXT NOT NULL,           -- repo-relative
  mtime      INTEGER NOT NULL,
  size       INTEGER NOT NULL,
  body_mtime INTEGER,                 -- mtime when body was pulled; NULL = none
  UNIQUE(repo_id, path)
);
CREATE INDEX IF NOT EXISTS file_by_mtime ON file(mtime DESC);
CREATE INDEX IF NOT EXISTS file_by_repo  ON file(repo_id, path);

CREATE VIRTUAL TABLE IF NOT EXISTS body USING fts5(
  text, tokenize='unicode61 remove_diacritics 2'
);
-- body.rowid is always file.id

CREATE TABLE IF NOT EXISTS gh(
  nwo TEXT PRIMARY KEY, name TEXT, private INTEGER,
  pushed_at TEXT, description TEXT, url TEXT
);

CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


def connect(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def get_meta(db, k, default=None):
    row = db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return row["v"] if row else default


def set_meta(db, k, v):
    db.execute("INSERT INTO meta(k,v) VALUES(?,?) "
               "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))


# ---------------------------------------------------------------- merge

def merge_host(db, host, doc, meta_for):
    """Fold one scan document into the index.

    meta_for(path, name, remote) -> dict with a theme, supplied by refresh.py
    so this module stays free of tagging concerns.

    Returns (n_repos, n_new, n_changed, n_gone).
    """
    seen_repos = []
    new = changed = gone = 0

    for r in doc["repos"]:
        extra = meta_for(r["path"], r["name"], r.get("remote"))
        db.execute(
            "INSERT INTO repo(host,path,name,theme,remote,"
            "                 branch,last_commit,mtime,n_files,n_bytes) "
            "VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(host,path) DO UPDATE SET "
            "  name=excluded.name, theme=excluded.theme, remote=excluded.remote,"
            "  branch=excluded.branch, last_commit=excluded.last_commit,"
            "  mtime=excluded.mtime, n_files=excluded.n_files,"
            "  n_bytes=excluded.n_bytes",
            (host, r["path"], r["name"], extra.get("theme", "UNTAGGED"),
             r.get("remote"), r.get("branch"), r.get("last_commit"),
             r.get("mtime", 0), len(r["files"]), r.get("bytes", 0)))
        repo_id = db.execute("SELECT id FROM repo WHERE host=? AND path=?",
                             (host, r["path"])).fetchone()["id"]
        seen_repos.append(repo_id)

        have = {row["path"]: (row["id"], row["mtime"], row["size"])
                for row in db.execute(
                    "SELECT id,path,mtime,size FROM file WHERE repo_id=?",
                    (repo_id,))}

        ins, upd = [], []
        for path, mtime, size in r["files"]:
            prev = have.pop(path, None)
            if prev is None:
                ins.append((repo_id, path, mtime, size))
            elif prev[1] != mtime or prev[2] != size:
                upd.append((mtime, size, prev[0]))

        if ins:
            db.executemany(
                "INSERT INTO file(repo_id,path,mtime,size) VALUES(?,?,?,?)", ins)
            new += len(ins)
        if upd:
            # body_mtime is left alone: refresh.py re-pulls where it lags mtime
            db.executemany(
                "UPDATE file SET mtime=?, size=? WHERE id=?", upd)
            changed += len(upd)
        if have:                                   # whatever is left vanished
            ids = [(v[0],) for v in have.values()]
            db.executemany("DELETE FROM body WHERE rowid=?", ids)
            db.executemany("DELETE FROM file WHERE id=?", ids)
            gone += len(ids)

    # repos that disappeared from this host entirely
    placeholders = ",".join("?" * len(seen_repos)) or "NULL"
    stale = [row["id"] for row in db.execute(
        "SELECT id FROM repo WHERE host=? AND id NOT IN (%s)" % placeholders,
        [host] + seen_repos)]
    for rid in stale:
        db.executemany("DELETE FROM body WHERE rowid=?",
                       [(row["id"],) for row in
                        db.execute("SELECT id FROM file WHERE repo_id=?", (rid,))])
        db.execute("DELETE FROM file WHERE repo_id=?", (rid,))
        db.execute("DELETE FROM repo WHERE id=?", (rid,))

    set_meta(db, host + "_as_of", int(time.time()))
    return len(seen_repos), new, changed, gone


# ---------------------------------------------------------------- reads

def repos(db, theme=None, host=None, flat=False):
    sql = ("SELECT * FROM repo WHERE 1=1"
           + (" AND theme=?" if theme else "")
           + (" AND host=?" if host else "")
           + (" ORDER BY mtime DESC" if flat
              else " ORDER BY theme, mtime DESC"))
    args = [x for x in (theme, host) if x]
    return db.execute(sql, args).fetchall()


def resolve_repo(db, ref):
    """Accept a bare name, a path, or host:name.
    Returns a list of matching rows (caller decides what ambiguity means)."""
    host = None
    if ":" in ref:
        host, ref = ref.split(":", 1)
    sql = ("SELECT * FROM repo WHERE (name=? OR path=?)"
           + (" AND host=?" if host else "") + " ORDER BY mtime DESC")
    args = [ref, ref] + ([host] if host else [])
    rows = db.execute(sql, args).fetchall()
    if rows:
        return rows
    sql = ("SELECT * FROM repo WHERE (name LIKE ? OR path LIKE ?)"
           + (" AND host=?" if host else "") + " ORDER BY mtime DESC")
    args = ["%" + ref + "%", "%" + ref + "%"] + ([host] if host else [])
    return db.execute(sql, args).fetchall()


def children(db, repo_id, prefix=""):
    """One level of the tree under prefix. Returns (dirs, files)."""
    like = prefix + "%" if prefix else "%"
    cut = len(prefix)
    dirs, files = set(), []
    for row in db.execute(
            "SELECT id,path,mtime,size,body_mtime FROM file "
            "WHERE repo_id=? AND path LIKE ? ORDER BY path", (repo_id, like)):
        rest = row["path"][cut:]
        slash = rest.find("/")
        if slash == -1:
            files.append(row)
        else:
            dirs.add(rest[:slash])
    return sorted(dirs), files


def find_names(db, q, host=None, repo_id=None, limit=50):
    sql = ("SELECT r.host,r.name AS repo,r.path AS repo_path,f.id,f.path,"
           "       f.mtime,f.size "
           "FROM file f JOIN repo r ON r.id=f.repo_id "
           "WHERE f.path LIKE ?"
           + (" AND r.host=?" if host else "")
           + (" AND f.repo_id=?" if repo_id else "")
           + " ORDER BY f.mtime DESC LIMIT ?")
    args = ["%" + q + "%"] + [x for x in (host, repo_id) if x] + [limit]
    return db.execute(sql, args).fetchall()


def fts_query(q):
    """Make arbitrary user text safe for FTS5.

    Bare text goes through as a phrase: unquoted, FTS5 reads '-' as NOT and
    'foo:bar' as a column filter, so `orbit find hash-chained` died with
    "no such column: chained". A leading '=' opts into raw FTS5 syntax
    (AND/OR/NEAR/prefix*) for when you actually want it.
    """
    q = q.strip()
    if q.startswith("="):
        return q[1:]
    return '"%s"' % q.replace('"', '""')


def find_content(db, q, host=None, repo_id=None, limit=50):
    sql = ("SELECT r.host,r.name AS repo,r.path AS repo_path,f.id,f.path,"
           "       snippet(body,0,'[',']','...',12) AS snip "
           "FROM body JOIN file f ON f.id=body.rowid "
           "          JOIN repo r ON r.id=f.repo_id "
           "WHERE body MATCH ?"
           + (" AND r.host=?" if host else "")
           + (" AND f.repo_id=?" if repo_id else "")
           + " ORDER BY rank LIMIT ?")
    args = [fts_query(q)] + [x for x in (host, repo_id) if x] + [limit]
    return db.execute(sql, args).fetchall()


def body_of(db, file_id):
    row = db.execute("SELECT text FROM body WHERE rowid=?", (file_id,)).fetchone()
    return row["text"] if row else None


def remote_nwo(url):
    """'git@github.com:Someone/chat-bot.git' -> 'someone/chat-bot'.

    Not rstrip('.git'): that strips any trailing '.', 'g', 'i' or 't', which
    turned chat-bot.git into chat-bo and made `orbit gaps` claim cloned
    repos were missing.
    """
    if not url:
        return None
    u = url.strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    u = u.replace(":", "/")
    parts = [x for x in u.split("/") if x]
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else None


def gaps(db):
    """(on GitHub but not cloned, cloned but never pushed)."""
    cloned = {remote_nwo(r["remote"]) for r in repos(db)}
    cloned.discard(None)
    missing = [g for g in db.execute("SELECT * FROM gh ORDER BY pushed_at DESC")
               if g["nwo"].lower() not in cloned]
    never = [r for r in repos(db, flat=True) if not r["remote"]]
    return missing, never


def counts(db):
    return {
        "repos": db.execute("SELECT COUNT(*) c FROM repo").fetchone()["c"],
        "files": db.execute("SELECT COUNT(*) c FROM file").fetchone()["c"],
        "bodies": db.execute("SELECT COUNT(*) c FROM body").fetchone()["c"],
    }
