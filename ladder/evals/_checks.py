"""Every stage's checks. Stage N's test runs check1..checkN, so earlier stages stay honest."""
import json
import os
import random

import evals


def has(*names):
    for name in names:
        assert hasattr(evals, name), "no function called %s yet" % name


def write(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def bad_file(lines, line_no, words):
    write("bad.jsonl", lines)
    try:
        evals.load_cases("bad.jsonl")
    except ValueError as e:
        msg = str(e)
        assert ("line %d" % line_no) in msg, "the error should name the bad line ('line %d'), got %r" % (line_no, msg)
        assert words in msg, "the error for line %d should mention %r, got %r" % (line_no, words, msg)
    else:
        raise AssertionError("load_cases should raise ValueError for this file (problem on line %d):\n%s" % (line_no, "\n".join(lines)))


def check1():
    has("load_cases")
    write("cases.jsonl", ['{"id": "q1", "input": "2+2", "expected": "4"}',
                          '',
                          '{"id": "q2", "input": "capital of France", "expected": "Paris", "tags": ["geo"]}'])
    got = evals.load_cases("cases.jsonl")
    assert isinstance(got, list), "load_cases should return a list, got %s" % type(got).__name__
    assert len(got) == 2, "2 cases in the file (blank lines are skipped), got %d: %r" % (len(got), got)
    assert got[0] == {"id": "q1", "input": "2+2", "expected": "4"}, "the first case should be the dict from line 1, got %r" % (got[0],)
    assert got[1].get("tags") == ["geo"], "extra fields like tags must be kept, got %r" % (got[1],)
    good = '{"id": "a", "input": "x", "expected": "y"}'
    bad_file([good, '{"id": "b", "input": "x", "expected": ', good.replace('"a"', '"c"')], 2, "JSON")
    bad_file([good, good.replace('"a"', '"b"'), '{"id": "c", "input": "x"}'], 3, "expected")
    bad_file(['{"input": "x", "expected": "y"}'], 1, "id")
    bad_file([good, '', good], 3, "duplicate")
    bad_file(['[1, 2, 3]'], 1, "object")


def grade(fn, output, expected, want, **kw):
    got = fn(output, expected, **kw)
    assert isinstance(got, tuple) and len(got) == 2, \
        "%s(...) should return a pair (passed, reason), got %r" % (fn.__name__, got)
    passed, reason = got
    assert passed is want, "%s(%r, %r) should say passed=%r, got %r (reason: %r)" % (fn.__name__, output, expected, want, passed, reason)
    assert isinstance(reason, str) and reason.strip(), "%s should always give a reason string, got %r" % (fn.__name__, reason)
    return reason


def check2():
    has("exact", "normalized", "contains_all", "numeric")
    grade(evals.exact, "Paris", "Paris", True)
    reason = grade(evals.exact, "paris", "Paris", False)
    assert "Paris" in reason and "paris" in reason, "a failing reason should show what was expected and what came out, got %r" % reason
    grade(evals.normalized, "  the  Paris!! ", "The paris", True)
    grade(evals.normalized, "Hello,\n  World.", "hello world", True)
    grade(evals.normalized, "Lyon", "Paris", False)
    grade(evals.contains_all, "Paris is the capital of France", ["paris", "France"], True)
    reason = grade(evals.contains_all, "Paris is lovely", ["Paris", "France", "capital"], False)
    assert "France" in reason and "capital" in reason, "the reason should list the missing keywords, got %r" % reason
    grade(evals.numeric, " 3.1416 ", "3.1415", True)
    grade(evals.numeric, "42", 42, True)
    grade(evals.numeric, "42.5", "42", False)
    grade(evals.numeric, "42.5", "42", True, tol=0.5)
    grade(evals.numeric, "about 42", "42", False)


def run_ok(result, n):
    assert isinstance(result, dict), "run should return a dict, got %s" % type(result).__name__
    for key in ["results", "pass_rate"]:
        assert key in result, "run's dict needs a %r key, keys: %r" % (key, sorted(result))
    assert len(result["results"]) == n, "one result per case: want %d, got %d" % (n, len(result["results"]))
    return result


def capitals(q):
    if q == "boom":
        raise RuntimeError("model timed out")
    return {"France": "Paris", "Italy": "Rome", "Spain": "Barcelona"}.get(q, "?")


CAPS = [{"id": "fr", "input": "France", "expected": "paris"},
        {"id": "boom", "input": "boom", "expected": "x"},
        {"id": "it", "input": "Italy", "expected": "Rome"},
        {"id": "es", "input": "Spain", "expected": "Madrid"}]


def check3():
    has("run")
    got = run_ok(evals.run(CAPS, capitals, evals.normalized), 4)
    ids = [r.get("id") for r in got["results"]]
    assert ids == ["fr", "boom", "it", "es"], "results should be in case order with their ids, got %r" % ids
    for r in got["results"]:
        for key in ["id", "output", "pass", "reason"]:
            assert key in r, "each result needs %r, got %r" % (key, r)
    fr, boom, it, es = got["results"]
    assert fr["pass"] is True and fr["output"] == "Paris", "France -> 'Paris' passes normalized vs 'paris', got %r" % (fr,)
    assert es["pass"] is False and es["output"] == "Barcelona", "Spain -> 'Barcelona' is a fail, got %r" % (es,)
    assert boom["pass"] is False and boom["output"] is None, "a system that raises: pass False and output None, got %r" % (boom,)
    assert boom["reason"].startswith("error:") and "model timed out" in boom["reason"] and "RuntimeError" in boom["reason"], \
        "the reason for a crash should start 'error:' and hold the exception type and text, got %r" % (boom["reason"],)
    assert got["pass_rate"] == 0.5, "2 of 4 passed: pass_rate should be 0.5, got %r" % (got["pass_rate"],)
    empty = evals.run([], capitals, evals.exact)
    assert empty["results"] == [] and empty["pass_rate"] == 0.0, "no cases: no results and pass_rate 0.0 (not a crash), got %r" % (empty,)


class Judge:
    def __init__(self, replies):
        self.replies = replies
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        reply = self.replies[len(self.prompts) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply


def check4():
    has("judge_prompt", "parse_verdict", "llm_judge")
    p = evals.judge_prompt("Rome is the capital", "Rome")
    assert isinstance(p, str) and "Rome is the capital" in p and "PASS" in p and "FAIL" in p, \
        "judge_prompt should hold the answer, the reference and the words PASS and FAIL, got %r" % (p,)
    table = [("PASS\nsays Rome", ("pass", "says Rome")),
             ("**FAIL** - wrong city", ("fail", "wrong city")),
             ("\n  pass: fine\nreally fine", ("pass", "fine really fine")),
             ("Fail", ("fail", ""))]
    for text, want in table:
        got = evals.parse_verdict(text)
        assert got == want, "parse_verdict(%r) should be %r, got %r" % (text, want, got)
    for text in ["", "   \n", "I think this is correct", "The answer: PASS"]:
        got = evals.parse_verdict(text)
        assert isinstance(got, tuple) and got[0] == "judge_error", \
            "parse_verdict(%r) can't be read with certainty: it should give ('judge_error', ...), got %r" % (text, got)
    judge = Judge(["PASS good", "FAIL no", "hmm, maybe?", ConnectionError("judge down")])
    cases = [{"id": i, "input": i, "expected": "ref-" + i} for i in ["a", "b", "c", "d"]]
    got = run_ok(evals.run(cases, lambda q: "ans-" + q, evals.llm_judge(judge)), 4)
    assert len(judge.prompts) == 4 and "ans-a" in judge.prompts[0] and "ref-a" in judge.prompts[0], \
        "the judge should get one prompt per case, holding the answer and the reference: %r" % (judge.prompts[:1],)
    status = [r.get("status") for r in got["results"]]
    assert status == ["pass", "fail", "judge_error", "judge_error"], \
        "statuses should be pass, fail, judge_error (unreadable), judge_error (judge raised), got %r" % (status,)
    assert [r["pass"] for r in got["results"]] == [True, False, False, False], "a judge_error never counts as a pass"
    assert got.get("counts") == {"pass": 1, "fail": 1, "error": 0, "judge_error": 2}, \
        "run should return counts per status, want %r, got %r" % ({"pass": 1, "fail": 1, "error": 0, "judge_error": 2}, got.get("counts"))
    got = evals.run(CAPS, capitals, evals.normalized)
    assert [r["status"] for r in got["results"]] == ["pass", "error", "pass", "fail"], \
        "a system that raises gets status 'error': want pass, error, pass, fail, got %r" % ([r["status"] for r in got["results"]],)


def flaky_system():
    calls = {}
    rng = random.Random(4)

    def system(q):
        calls[q] = calls.get(q, 0) + 1
        if q == "always":
            return "yes"
        if q == "never":
            return "no"
        if q == "every-other":
            return "yes" if calls[q] % 2 == 1 else "no"
        if q == "first-crash":
            if calls[q] == 1:
                raise TimeoutError("slow")
            return "yes"
        return "yes" if rng.random() < 0.7 else "no"
    return system, calls


def check5():
    has("run_trials")
    cases = [{"id": q, "input": q, "expected": "yes"} for q in ["always", "never", "every-other", "first-crash", "coin"]]
    system, calls = flaky_system()
    got = evals.run_trials(cases, system, evals.exact, 200)
    assert calls["always"] == 200 and calls["coin"] == 200, "n=200: each case should be run 200 times, calls were %r" % (calls,)
    rates = got.get("rates")
    assert isinstance(rates, dict), "run_trials should return a dict with 'rates': case id -> fraction passed, got %r" % (got,)
    for case_id, want in [("always", 1.0), ("never", 0.0), ("every-other", 0.5), ("first-crash", 199 / 200)]:
        assert abs(rates[case_id] - want) < 1e-9, "rates[%r] should be %r, got %r" % (case_id, want, rates[case_id])
    assert 0.6 < rates["coin"] < 0.8, "'coin' passes 70%% of the time: its rate should be near 0.7, got %r" % (rates["coin"],)
    assert got.get("flaky") == ["every-other", "first-crash", "coin"], \
        "flaky = ids that sometimes pass and sometimes fail, in case order, got %r" % (got.get("flaky"),)
    want = sum(rates.values()) / 5
    assert abs(got.get("pass_at_1", -1) - want) < 1e-9, "pass_at_1 is the mean of the per-case rates: %r, got %r" % (want, got.get("pass_at_1"))
    try:
        evals.run_trials(cases, system, evals.exact, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("run_trials with n=0 should raise ValueError")


def fake_run(passes):
    results = [{"id": "c%d" % i, "output": "", "pass": p, "reason": "", "status": "pass" if p else "fail", "tags": []}
               for i, p in enumerate(passes)]
    rate = sum(passes) / len(passes)
    return {"results": results, "pass_rate": rate,
            "counts": {"pass": sum(passes), "fail": len(passes) - sum(passes), "error": 0, "judge_error": 0}}


def check6():
    has("sign_test", "compare")
    for wins, losses, want in [(10, 0, 2 / 1024), (3, 0, 0.25), (6, 1, 0.125), (0, 0, 1.0), (2, 2, 1.0), (1, 9, 22 / 1024)]:
        got = evals.sign_test(wins, losses)
        assert abs(got - want) < 1e-12, "sign_test(%d, %d) should be %r, got %r" % (wins, losses, want, got)
    before = fake_run([True, True, False, False, True, False])
    after = fake_run([True, False, True, True, True, False])
    got = evals.compare(before, after)
    assert got.get("regressions") == ["c1"], "c1 passed before and fails now: regressions should be ['c1'], got %r" % (got.get("regressions"),)
    assert got.get("improvements") == ["c2", "c3"], "c2 and c3 failed before and pass now, got %r" % (got.get("improvements"),)
    assert abs(got.get("delta", 99) - 1 / 6) < 1e-9, "delta = after pass_rate - before pass_rate = 1/6, got %r" % (got.get("delta"),)
    assert abs(got.get("p_value", 99) - 1.0) < 1e-12 and got.get("significant") is False, \
        "2 wins vs 1 loss is noise: p_value 1.0, significant False, got %r" % (got,)
    before = fake_run([False] * 12)
    after = fake_run([True] * 10 + [False] * 2)
    got = evals.compare(before, after)
    assert got["significant"] is True and abs(got["p_value"] - 2 / 1024) < 1e-12, \
        "10 improvements and no regressions is real: p %r, significant True, got %r" % (2 / 1024, got)
    extra = fake_run([True, True, True])
    extra["results"][2]["id"] = "new-case"
    got = evals.compare(fake_run([False, True, False]), extra)
    assert got["improvements"] == ["c0"] and got["regressions"] == [], \
        "a case that is only in one run is skipped, got %r" % (got,)


SLICED = [{"id": "m1", "input": "2+2", "expected": "4", "tags": ["math"]},
          {"id": "m2", "input": "3*3", "expected": "9", "tags": ["math", "hard"]},
          {"id": "g1", "input": "France", "expected": "Paris", "tags": ["geo"]},
          {"id": "g2", "input": "Spain", "expected": "Madrid", "tags": ["geo", "hard"]},
          {"id": "x1", "input": "hi", "expected": "hello"}]


def check7():
    has("slices")
    answers = {"2+2": "4", "3*3": "6", "France": "Paris", "Spain": "Madrid", "hi": "yo"}
    got = evals.run(SLICED, lambda q: answers[q], evals.exact)
    assert [r.get("tags") for r in got["results"]] == [["math"], ["math", "hard"], ["geo"], ["geo", "hard"], []], \
        "each result should carry its case's tags ([] when the case has none), got %r" % ([r.get("tags") for r in got["results"]],)
    rows = evals.slices(got)
    want = [{"tag": "untagged", "n": 1, "passed": 0, "pass_rate": 0.0},
            {"tag": "hard", "n": 2, "passed": 1, "pass_rate": 0.5},
            {"tag": "math", "n": 2, "passed": 1, "pass_rate": 0.5},
            {"tag": "geo", "n": 2, "passed": 2, "pass_rate": 1.0}]
    assert rows == want, "slices should be worst first (ties by tag name), untagged cases under 'untagged':\nwant %r\ngot  %r" % (want, rows)


LOOP = [{"id": "add", "input": "2+2", "expected": "4", "tags": ["math"]},
        {"id": "mul", "input": "3*3", "expected": "9", "tags": ["math"]},
        {"id": "sub", "input": "9-4", "expected": "5", "tags": ["math"]},
        {"id": "fr", "input": "France", "expected": "Paris", "tags": ["geo"]},
        {"id": "it", "input": "Italy", "expected": "Rome", "tags": ["geo"]},
        {"id": "jp", "input": "Japan", "expected": "Tokyo", "tags": ["geo"]},
        {"id": "hi", "input": "greet", "expected": "hello", "tags": ["chat"]},
        {"id": "bye", "input": "leave", "expected": "goodbye", "tags": ["chat"]}]
RIGHT = {c["input"]: c["expected"] for c in LOOP}


def version(broken):
    def system(q):
        tag = [c["tags"][0] for c in LOOP if c["input"] == q][0]
        if tag in broken:
            return "no idea"
        return RIGHT[q].upper() + "!"
    return system


def section(text, title):
    head = "## " + title
    assert head in text, "the report should have a %r section:\n%s" % (head, text)
    body = text.split(head, 1)[1].split("\n## ", 1)[0]
    return [line[2:].strip() for line in body.split("\n") if line.startswith("- ")]


def check8():
    has("save_baseline", "load_baseline", "report", "evaluate")
    assert evals.load_baseline("nothing-here.json") is None, "load_baseline of a missing file should return None"
    first = evals.run(SLICED, lambda q: "4", evals.exact)
    evals.save_baseline(first, "b.json")
    back = evals.load_baseline("b.json")
    assert back == json.loads(json.dumps(first)), "load_baseline should give back what save_baseline wrote"
    path = "baseline.json"
    v1, text1 = evals.evaluate(LOOP, version({"math"}), evals.normalized, path)
    assert v1["pass_rate"] == 5 / 8, "v1 gets math wrong: pass_rate 5/8, got %r" % (v1["pass_rate"],)
    assert text1.startswith("# Eval report"), "the report starts with '# Eval report', got:\n%s" % text1
    assert "pass rate: 62.5% (5/8)" in text1, "the report should say 'pass rate: 62.5% (5/8)', got:\n%s" % text1
    assert "no baseline" in text1, "the first run has nothing to compare to: say 'no baseline', got:\n%s" % text1
    assert section(text1, "Worst slices")[0] == "math: 0.0% (0/3)", "worst slice first, as 'math: 0.0% (0/3)', got:\n%s" % text1
    assert os.path.exists(path), "the first evaluate should save its run as the baseline"
    v2, text2 = evals.evaluate(LOOP, version({"geo"}), evals.normalized, path)
    assert "change: +0.0 points" in text2, "v2 fixes 3 and breaks 3: 'change: +0.0 points', got:\n%s" % text2
    assert section(text2, "Regressions") == ["fr", "it", "jp"], "v2 breaks geo: regressions fr, it, jp, got:\n%s" % text2
    assert section(text2, "Improvements") == ["add", "mul", "sub"], "v2 fixes math: improvements add, mul, sub, got:\n%s" % text2
    assert "significant: no (p=1.0000)" in text2, "3 wins vs 3 losses: 'significant: no (p=1.0000)', got:\n%s" % text2
    assert section(text2, "Worst slices") == ["geo: 0.0% (0/3)", "chat: 100.0% (2/2)", "math: 100.0% (3/3)"], \
        "worst slices (at most 3), worst first, got:\n%s" % text2
    assert evals.load_baseline(path)["pass_rate"] == 5 / 8 and not evals.load_baseline(path)["results"][0]["pass"], \
        "v2 has regressions: the baseline must stay v1, it was overwritten"
    v3, text3 = evals.evaluate(LOOP, version(set()), evals.normalized, path)
    assert section(text3, "Regressions") == ["none"] and section(text3, "Improvements") == ["add", "mul", "sub"], \
        "v3 vs the v1 baseline: no regressions ('- none'), improvements add, mul, sub, got:\n%s" % text3
    assert "change: +37.5 points" in text3, "v3 vs v1: 'change: +37.5 points', got:\n%s" % text3
    assert evals.load_baseline(path)["pass_rate"] == 1.0, "v3 has no regressions: it becomes the new baseline"


CHECKS = [check1, check2, check3, check4, check5, check6, check7, check8]


def run_up_to(n):
    for check in CHECKS[:n]:
        check()
