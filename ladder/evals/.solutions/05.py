import json
import string


def load_cases(path):
    cases = []
    seen = set()
    with open(path) as f:
        for number, line in enumerate(f, start=1):
            if line.strip() == "":
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError("line %d: not valid JSON" % number)
            if not isinstance(case, dict):
                raise ValueError("line %d: each line must be a JSON object" % number)
            for field in ["id", "input", "expected"]:
                if field not in case:
                    raise ValueError("line %d: missing %r" % (number, field))
            if case["id"] in seen:
                raise ValueError("line %d: duplicate id %r" % (number, case["id"]))
            seen.add(case["id"])
            cases.append(case)
    return cases


def exact(output, expected):
    if output == expected:
        return True, "exact match"
    return False, "expected %r, got %r" % (expected, output)


def normalize(text):
    text = text.lower()
    for mark in string.punctuation:
        text = text.replace(mark, "")
    return " ".join(text.split())


def normalized(output, expected):
    if normalize(output) == normalize(expected):
        return True, "match after normalizing"
    return False, "expected %r, got %r" % (expected, output)


def contains_all(output, expected):
    missing = []
    for word in expected:
        if word.lower() not in output.lower():
            missing.append(word)
    if missing:
        return False, "missing: " + ", ".join(missing)
    return True, "all keywords present"


def numeric(output, expected, tol=0.001):
    try:
        got = float(output)
    except ValueError:
        return False, "not a number: %r" % (output,)
    if abs(got - float(expected)) <= tol:
        return True, "within %s of %s" % (tol, expected)
    return False, "expected %s, got %s" % (expected, got)


def judge_prompt(output, expected):
    return ("You are grading an answer.\n"
            "Reference answer: %s\n"
            "Answer to grade: %s\n"
            "Reply with PASS or FAIL on the first line, then one line saying why." % (expected, output))


def parse_verdict(text):
    lines = []
    for line in text.split("\n"):
        if line.strip() != "":
            lines.append(line.strip())
    if not lines:
        return "judge_error", "empty reply"
    first = lines[0].strip("*# ")
    word = first[:4].upper()
    if word != "PASS" and word != "FAIL":
        return "judge_error", "could not read: %r" % (text[:80],)
    rest = [first[4:].strip("*:-., ")] + lines[1:]
    return word.lower(), " ".join(rest).strip()


def llm_judge(judge):
    def grade(output, expected):
        try:
            reply = judge(judge_prompt(output, expected))
        except Exception as e:
            return False, "judge_error: judge raised %s: %s" % (type(e).__name__, e)
        verdict, reason = parse_verdict(reply)
        if verdict == "judge_error":
            return False, "judge_error: " + reason
        return verdict == "pass", reason
    return grade


def run(cases, system, grader):
    results = []
    counts = {"pass": 0, "fail": 0, "error": 0, "judge_error": 0}
    for case in cases:
        try:
            output = system(case["input"])
        except Exception as e:
            output = None
            passed = False
            reason = "error: %s: %s" % (type(e).__name__, e)
            status = "error"
        else:
            passed, reason = grader(output, case["expected"])
            if passed:
                status = "pass"
            elif reason.startswith("judge_error"):
                status = "judge_error"
            else:
                status = "fail"
        counts[status] += 1
        results.append({"id": case["id"], "output": output, "pass": passed, "reason": reason,
                        "status": status})
    if results:
        pass_rate = counts["pass"] / len(results)
    else:
        pass_rate = 0.0
    return {"results": results, "pass_rate": pass_rate, "counts": counts}


def run_trials(cases, system, grader, n):
    if n < 1:
        raise ValueError("n must be at least 1")
    wins = {}
    for case in cases:
        wins[case["id"]] = 0
    for trial in range(n):
        for result in run(cases, system, grader)["results"]:
            if result["pass"]:
                wins[result["id"]] += 1
    rates = {}
    flaky = []
    for case in cases:
        rate = wins[case["id"]] / n
        rates[case["id"]] = rate
        if 0 < rate < 1:
            flaky.append(case["id"])
    if rates:
        pass_at_1 = sum(rates.values()) / len(rates)
    else:
        pass_at_1 = 0.0
    return {"pass_at_1": pass_at_1, "rates": rates, "flaky": flaky}
