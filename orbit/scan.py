#!/usr/bin/env python3
"""orbit scanner -- walks one home directory and prints one gzipped JSON doc.

Runs in two places, unchanged:
  - locally, imported by refresh.py
  - on every other Mac, piped to /usr/bin/python3 over ssh stdin

macOS ships /usr/bin/python3 as 3.9, so: no match statements, no X | Y
annotations at runtime, no walrus in comprehension scope tricks. Stdlib only.
Nothing is ever installed on the other Macs.

The ignore rules live here on purpose. This file is the thing that gets shipped
to the other host, so the rules travel with it and cannot drift out of sync.

Usage:
    python3 scan.py [extra_root ...] [!ignored_path ...]   # both home-relative
    ssh other-mac /usr/bin/python3 - < scan.py
"""

import configparser
import gzip
import io
import json
import os
import socket
import sys
import time

# Never descended while looking for repo roots. These hold no projects and a
# great deal of junk -- a photo library alone can be 150k files / 19 GB.
# Downloads is deliberately absent: people do clone repos into it.
PRUNE_ROOT = {
    "Library", "Pictures", "Movies", "Music", "Applications", "Public",
    ".Trash", ".cache", ".npm", ".cargo", ".rustup", ".ollama", ".gem",
    ".grok", ".vscode", ".docker", ".android", "go", "Parallels",
    "VirtualBox VMs",
}

# Skipped by basename at any depth inside a repo.
# .build matters: one Swift package's .build was 31,843 files / 2.0 GB hiding
# 107 real ones.
IGNORE_NAMES = {
    ".git", "node_modules", ".venv", "venv", "env", "dist", "build", ".build",
    ".next", ".nuxt", "out", "target", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".tox", "vendor", "Pods", ".terraform",
    ".gradle", ".swiftpm", "DerivedData", "coverage", ".parcel-cache",
    ".turbo", ".pnpm-store", ".svelte-kit", ".angular", "Carthage",
}

# Skipped by home-relative prefix, from "ignore" in config.json (passed in as
# !path arguments). For a repo whose one subdirectory is gigabytes of runtime
# data: a basename rule cannot express that.
IGNORE_PATHS = ()

# Extensions whose bodies are worth pulling into the content index later.
# Lives here so scan.py stays the single source of truth for what counts as
# source text.
TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".rs", ".go", ".rb",
    ".swift", ".m", ".mm", ".h", ".c", ".cc", ".cpp", ".hpp", ".java", ".kt",
    ".cs", ".php", ".lua", ".pl", ".r", ".jl", ".scala", ".clj", ".ex", ".exs",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    ".sql", ".graphql", ".proto",
    ".html", ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".properties", ".plist", ".xml", ".csv", ".tsv",
    ".md", ".mdx", ".markdown", ".rst", ".txt", ".org", ".tex",
    ".ipynb", ".tcss", ".mmd", ".dot", ".gitignore", ".dockerignore",
}
# Extensionless files that are still text.
TEXT_NAMES = {
    "Makefile", "Dockerfile", "Justfile", "Procfile", "Rakefile", "Gemfile",
    "Brewfile", "Caddyfile", "Vagrantfile", "LICENSE", "README", "CHANGELOG",
    "AUTHORS", "NOTICE", "CODEOWNERS", ".gitignore", ".gitattributes",
    ".editorconfig", ".zshrc", ".bashrc", ".profile",
}

ROOT_DEPTH = 3          # how deep to hunt for repo roots below $HOME
MAX_BODY = 400_000      # bytes; larger files get metadata but never a body


def is_text(name):
    """True when this filename looks like source text worth indexing."""
    if name in TEXT_NAMES:
        return True
    dot = name.rfind(".")
    return dot > 0 and name[dot:].lower() in TEXT_EXTS


def ignored_path(rel):
    """True when a home-relative path sits under one of the IGNORE_PATHS."""
    for p in IGNORE_PATHS:
        if rel == p or rel.startswith(p + "/"):
            return True
    return False


def find_roots(home, extra):
    """Breadth-first hunt for project roots: any dir holding .git, plus any
    explicitly named extra root that exists. A root is never descended into
    while looking for further roots."""
    roots = []
    seen = set()

    def add(rel):
        if rel and rel not in seen:
            seen.add(rel)
            roots.append(rel)

    frontier = [("", 0)]
    while frontier:
        rel, depth = frontier.pop()
        abs_dir = os.path.join(home, rel) if rel else home
        try:
            entries = list(os.scandir(abs_dir))
        except OSError:
            continue

        names = set()
        subdirs = []
        for e in entries:
            names.add(e.name)
            try:
                if e.is_dir(follow_symlinks=False):
                    subdirs.append(e.name)
            except OSError:
                pass

        if rel and ".git" in names:
            add(rel)
            continue                        # a repo is a leaf for discovery

        if depth >= ROOT_DEPTH:
            continue
        for name in subdirs:
            if name in PRUNE_ROOT:
                continue
            child = (rel + "/" + name) if rel else name
            if ignored_path(child):
                continue
            frontier.append((child, depth + 1))

    for rel in extra:
        rel = rel.strip("/")
        if rel and os.path.isdir(os.path.join(home, rel)):
            add(rel)
    return roots


def walk(home, root):
    """Every non-ignored file under one root, as (repo-relative, mtime, size).
    Also returns the byte total and the newest mtime seen."""
    files = []
    total = 0
    newest = 0
    base = os.path.join(home, root)
    stack = [""]
    while stack:
        sub = stack.pop()
        try:
            entries = list(os.scandir(os.path.join(base, sub) if sub else base))
        except OSError:
            continue
        for e in entries:
            if e.name in IGNORE_NAMES:
                continue
            rel = (sub + "/" + e.name) if sub else e.name
            if ignored_path(root + "/" + rel):
                continue
            try:
                if e.is_dir(follow_symlinks=False):
                    stack.append(rel)
                    continue
                if not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            mtime = int(st.st_mtime)
            files.append([rel, mtime, st.st_size])
            total += st.st_size
            if mtime > newest:
                newest = mtime
    return files, total, newest


def git_info(abs_root):
    """Branch, origin URL and last-ref-update time, read straight out of .git.

    Deliberately never shells out: 62 `git status` calls would cost ~30s and
    buy a dirty flag v1 can live without.
    ponytail: no dirty count; add `git status --porcelain` per repo if the
    half-done-work signal turns out to matter more than the 30s.
    """
    g = os.path.join(abs_root, ".git")
    if os.path.isfile(g):                       # worktree / submodule pointer
        try:
            with open(g) as fh:
                line = fh.read().strip()
            if line.startswith("gitdir:"):
                g = os.path.normpath(
                    os.path.join(abs_root, line.split(":", 1)[1].strip()))
        except OSError:
            return {}
    if not os.path.isdir(g):
        return {}

    out = {}
    try:
        with open(os.path.join(g, "HEAD")) as fh:
            head = fh.read().strip()
        if head.startswith("ref: refs/heads/"):
            out["branch"] = head[len("ref: refs/heads/"):]
        elif head:
            out["branch"] = head[:8]            # detached
    except OSError:
        pass

    # logs/HEAD moves on commit, checkout, pull, reset -- the best cheap proxy
    # for "when did this repo last change". Fall back to the loose ref.
    for cand in ("logs/HEAD", "refs/heads/" + out.get("branch", "")):
        try:
            out["last_commit"] = int(os.stat(os.path.join(g, cand)).st_mtime)
            break
        except OSError:
            continue

    try:
        cp = configparser.ConfigParser(strict=False)
        cp.read(os.path.join(g, "config"))
        for section in cp.sections():
            if section.replace('"', "").strip() == "remote origin":
                url = cp.get(section, "url", fallback=None)
                if url:
                    out["remote"] = url.strip()
                break
    except Exception:
        pass
    return out


def scan(home, extra_roots):
    started = time.time()
    repos = []
    for root in find_roots(home, extra_roots):
        abs_root = os.path.join(home, root)
        files, total, newest = walk(home, root)
        repo = {
            "path": root,
            "name": os.path.basename(root),
            "mtime": newest,
            "bytes": total,
            "files": files,
        }
        repo.update(git_info(abs_root))
        repos.append(repo)
    return {
        "home": home,
        "hostname": socket.gethostname(),
        "t": int(time.time()),
        "elapsed_ms": int((time.time() - started) * 1000),
        "repos": repos,
    }


def main(argv):
    global IGNORE_PATHS
    IGNORE_PATHS = tuple(a[1:].strip("/") for a in argv if a.startswith("!"))
    home = os.path.expanduser("~")
    doc = scan(home, [a for a in argv if not a.startswith("!")])
    raw = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    # mtime=0 keeps the output byte-stable for a given input, so two runs
    # over the same tree can be compared byte for byte.
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as gz:
        gz.write(raw)
    sys.stdout.buffer.write(buf.getvalue())
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main(sys.argv[1:])
