"""The ladder: interview-style build tasks, typed by hand, judged by tests.

A unit is a folder under ladder/<unit>/ in this repo holding NN.md (the lesson)
and NN_test.py (plain asserts that `import <unit>`). Your code is one growing
file, ~/ladder/<unit>.py. Stage N's test checks the whole contract of stage
N, so it doubles as the regression check for earlier stages.
Reference solutions in <unit>/.solutions/ are only for the content gate in
test_orbit.py; orbit never reads them. Stdlib only.
"""

import ast
import datetime
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile

UNITS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ladder")
WORK = os.path.expanduser("~/ladder")
PATH = os.path.expanduser("~/.config/orbit/ladder.json")
TIMEOUT = 5
CAP = 20000

# One line per stage for the capability ladder: what you can now build.
CAN = {"kv": ["store and read values in a dict",
              "name the moves with functions",
              "handle what isn't there",
              "walk all the data with loops",
              "turn functions into a class",
              "undo work with a transaction",
              "nest transactions with a stack",
              "expire keys with an injected clock"],
       "lru": ["evict the oldest when full",
               "track least recently used",
               "get the overwrite edge case right",
               "measure hits, misses, evictions",
               "make every operation O(1)",
               "build a doubly linked list by hand",
               "call back on eviction",
               "peek without side effects, resize"],
       "bank": ["model accounts as a class over a dict",
                "guard clauses: every failure returns early",
                "keep money exact: int cents, ValueError",
                "rank with sorted(key=lambda) and tuples",
                "log records, answer questions about the past",
                "run scheduled events before each operation",
                "merge state without losing anything",
                "one rule, one place, checked by invariants"],
       "crawler": ["crawl a link graph with BFS, cycle-safe",
                   "limit crawl depth, shortest path first",
                   "clean up messy links with urllib.parse",
                   "keep crawling past errors, with retries",
                   "fetch pages in parallel with threads",
                   "crawl concurrently with asyncio.gather",
                   "cap requests in flight with a Semaphore",
                   "enforce a page budget, cancel timeouts"],
       "bpe": ["turn text into UTF-8 bytes and back",
               "count every adjacent pair in a sequence",
               "replace a pair everywhere with one new id",
               "train BPE merges with an exact tie rule",
               "encode and decode any text, emoji included",
               "keep merges inside words (regex pre-split)",
               "special tokens that are never split",
               "save and load a tokenizer, same ids"],
       "gpt": ["measure a slope by nudging the input",
               "backprop through a graph (topo sort)",
               "add pow/exp/log/tanh, check the grads",
               "fit a Linear layer by gradient descent",
               "turn scores into probabilities, stably",
               "train and sample a bigram language model",
               "build causal self-attention",
               "assemble and train a tiny GPT"],
       "rag": ["cut documents into overlapping chunks",
               "weigh words with TF-IDF vectors",
               "rank by cosine with stable top-k",
               "score with BM25, beat raw TF-IDF",
               "keep an index correct as it grows",
               "build a budgeted prompt, or say idk",
               "measure retrieval: recall@k and MRR",
               "fuse words and embeddings with RRF"],
       "agent": ["keep a registry of tools the model can call",
                 "run a tool call, errors go back as text",
                 "write the model → tool → result loop",
                 "stop a model that never finishes",
                 "pull JSON out of a messy model reply",
                 "log every step's time and token cost",
                 "make risky tools wait for a human yes",
                 "trim context, keep prompt, task, newest"],
       "evals": ["load a JSONL dataset, errors name the line",
                 "grade answers four ways, each with a reason",
                 "run a whole eval without crashing on errors",
                 "use an LLM judge that never counts noise",
                 "measure pass@1 and find flaky cases",
                 "prove a change is real with a sign test",
                 "find the weakest slice of your dataset",
                 "auto-compare every run against a baseline"]}

# The climb, in order.
ORDER = [("kv", "key-value store"), ("lru", "LRU cache"), ("bank", "bank system"),
         ("crawler", "concurrent crawler"), ("bpe", "BPE tokenizer"), ("gpt", "tiny GPT"),
         ("rag", "RAG system · applied AI"), ("agent", "AI agent · applied AI"),
         ("evals", "eval harness · applied AI")]
NEXT_UP = "next track (ask Claude what's after evals)"


def done(p, unit):
    return len(unit_state(p, unit)["passed"]) >= len(stages(unit))


def current_unit(p):
    """First unit not finished (the last one when all are)."""
    for u, _ in ORDER:
        if not done(p, u):
            return u
    return ORDER[-1][0]


def stages(unit):
    """[(n, lesson_path, test_path)] in order."""
    out = []
    for md in sorted(glob.glob(os.path.join(UNITS, unit, "[0-9][0-9].md"))):
        n = int(os.path.basename(md)[:2])
        out.append((n, md, md[:-3] + "_test.py"))
    return out


def code_path(unit):
    return os.path.join(WORK, unit + ".py")


def run(code, test_path, unit, timeout=TIMEOUT):
    """Run one stage's test against `code` (the learner's file) in a fresh
    process in a temp dir. -> (ok, message). A fresh process means no stale
    import; a new session means a timeout kills everything that code started.
    ponytail: accident-proof, not adversary-proof."""
    tmp = tempfile.mkdtemp(prefix="ladder-")
    try:
        with open(os.path.join(tmp, unit + ".py"), "w") as f:
            f.write(code)
        shutil.copy(test_path, os.path.join(tmp, "check.py"))
        for helper in glob.glob(os.path.join(os.path.dirname(test_path), "_*.py")):
            shutil.copy(helper, tmp)                # shared test code, e.g. _speed.py
        p = subprocess.Popen([sys.executable, "-E", "-s", "-B", "check.py"], cwd=tmp,
                             env={"HOME": tmp, "PATH": "/usr/bin:/bin"},
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            out, _ = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            return False, ("still running after %ds: an infinite loop? "
                           "(a while whose condition never turns False)" % timeout)
        out = out[:CAP].decode("utf-8", "replace")
        return p.returncode == 0, explain(out, unit)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def explain(out, unit):
    """Turn a traceback into what the learner needs: the check that failed, or the
    error in HIS file with its line. Frames inside the test are noise."""
    if not out.strip():
        return "all checks pass"
    lines = out.rstrip().split("\n")
    last = lines[-1]
    if last.startswith("AssertionError"):
        return "✗ " + (last.partition(": ")[2] or "a check failed")
    mine = [i for i, l in enumerate(lines) if ('/%s.py"' % unit) in l]
    where = ""
    if mine:
        i = mine[-1]
        m = re.search(r"line (\d+)", lines[i])
        where = "your %s.py line %s:\n" % (unit, m.group(1) if m else "?")
        if i + 1 < len(lines) and not lines[i + 1].lstrip().startswith("File"):
            where += "    " + lines[i + 1].strip() + "\n"
    return "✗ your code crashed\n" + where + last


# ------------------------------------------------------------- progress

def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(p):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(p, f, indent=1)
    os.replace(tmp, PATH)


def unit_state(p, unit):
    u = p.setdefault(unit, {"passed": {}, "pasted": []})
    u.setdefault("shown", [])                   # stages where a line was revealed
    return u


def current(p, unit):
    """First stage not passed yet (the last one when all are done)."""
    u = unit_state(p, unit)
    ns = [n for n, _, _ in stages(unit)]
    for n in ns:
        if str(n) not in u["passed"]:
            return n
    return ns[-1]


def mark_pasted(p, unit, n):
    u = unit_state(p, unit)
    if n not in u["pasted"]:
        u["pasted"].append(n)


def mark_passed(p, unit, n, today=None):
    """-> 'unaided' | 'pasted' | 'shown'. A stage keeps its best grade."""
    u = unit_state(p, unit)
    grade = ("shown" if n in u["shown"] else
             "pasted" if n in u["pasted"] else "unaided")
    if u["passed"].get(str(n)) != "unaided":
        u["passed"][str(n)] = grade
    day = (today or datetime.date.today()).isoformat()
    days = p.setdefault("days", [])
    if day not in days:
        days.append(day)
    return grade


def streak(days, today=None):
    """Consecutive days with a pass, ending today (or yesterday: today
    isn't lost until it's over)."""
    today = today or datetime.date.today()
    have = set(days)
    d = today if today.isoformat() in have else today - datetime.timedelta(days=1)
    n = 0
    while d.isoformat() in have:
        n += 1
        d -= datetime.timedelta(days=1)
    return n


def ladder_text(p, unit):
    """The capability ladder: done, current, locked."""
    u = unit_state(p, unit)
    cur = current(p, unit)
    rows = []
    for i, can in enumerate(CAN.get(unit, []), 1):
        g = u["passed"].get(str(i))
        if g:
            rows.append("✓ %s%s" % (can, "" if g == "unaided" else "  (%s)" % g))
        elif i == cur:
            rows.append("▶ %s" % can)
        else:
            rows.append("🔒 %s" % can)
    return "\n".join(rows)


# ------------------------------------------------------------- review

REVIEW = """You are a senior engineer interviewing a beginner for an AI lab. They are
learning to write code by hand and must type every line themselves.

HARD RULE: never write code. No code blocks, no corrected lines, no function
bodies, not even one line of Python. You may name a built-in or method in
backticks (like `in` or `dict()`), nothing longer.

In at most 8 short lines:
1. If the checks fail: point at the line number that is wrong and ask ONE
   question that leads them to the fix. Do not state the fix.
2. If they pass: one thing done well, one thing an interviewer would push on
   (naming, a missing edge case, a simpler shape), as a question.
3. Explain at most one concept in plain words if they clearly lack it.

--- stage lesson ---
%s
--- their code (%s.py) ---
%s
--- test result ---
%s
"""


def review_prompt(lesson, unit, code, result):
    numbered = "\n".join("%3d  %s" % (i, l) for i, l in enumerate(code.split("\n"), 1))
    return REVIEW % (lesson, unit, numbered, result)


def leaks_code(text, blanks_ok=False):
    """True if a review contains a solution: a fence, or 2+ lines that parse
    as real Python statements (not a lone word or number). blanks_ok: a
    skeleton line with ___ in it is allowed (hint level 3)."""
    if "```" in text and not blanks_ok:
        return True
    n = 0
    for line in text.split("\n"):
        s = line.strip().strip("`")
        if not s or s.startswith("```") or (blanks_ok and "___" in s):
            continue
        try:                        # "if x:" alone is a block header: give it a body
            tree = ast.parse(s + "\n    pass" if s.endswith(":") else s)
        except SyntaxError:
            continue
        body = tree.body
        if body and not (len(body) == 1 and isinstance(body[0], ast.Expr)
                         and isinstance(body[0].value, (ast.Name, ast.Constant))):
            n += 1
    return n >= (1 if blanks_ok else 2)        # a skeleton may hold no finished line


# ------------------------------------------------------------- hints
# ctrl+h climbs these one press at a time; a new stage starts at 1 again.
# Levels 1-3 ask Claude, level 4+ reveal the reference solution one line
# at a time (local, instant) and mark the stage "shown".

HINT_LEVELS = {
    1: ("nudge", """Give a NUDGE, 2 sentences max. Say in plain words what the check
result means (or, if nothing was run yet, what the very first thing to type
is about), and name which part of the lesson to reread. No code at all."""),
    2: ("point", """POINT at the exact tool, 3 sentences max. Name the Python syntax or
concept they need next, quote the ONE line from the lesson's example that
uses it, and say in words how that line maps onto their task. Do not write
any line of their solution."""),
    3: ("shape", """Show the SHAPE of only the next piece they need: at most 4 lines of
Python where every name, key, value and expression they must choose is
replaced by ___ . EVERY line must contain at least one ___ . Keep keywords,
brackets, colons and indentation. Put it
in a ``` block, then one sentence on what goes in the blanks."""),
}


def hint_prompt(level, lesson, unit, code, result):
    numbered = "\n".join("%3d  %s" % (i, l) for i, l in enumerate(code.split("\n"), 1))
    return ("""You are a patient tutor for an absolute beginner who is stuck. They
must type every line themselves: help them take ONE small step, never more.

%s

--- stage lesson ---
%s
--- their code (%s.py) ---
%s
--- last check result ---
%s
""" % (HINT_LEVELS[level][1], lesson, unit, numbered, result or "not run yet"))


def solution_path(unit, n):
    return os.path.join(UNITS, unit, ".solutions", "%02d.py" % n)


def next_missing_line(solution, code):
    """The first line of the reference solution that the learner's code does not have
    yet (compared stripped, so indentation slips don't count). None when it
    has them all; then the bug is in order or detail, not a missing line.
    ponytail: exact-text match, so a correct-but-different line (other
    value, other name) still counts as missing; ast-level matching if that bites."""
    have = {l.strip() for l in code.split("\n")}
    lines = solution.split("\n")
    for i, l in enumerate(lines):
        if l.strip() and l.strip() not in have:
            return i + 1, l
    return None
