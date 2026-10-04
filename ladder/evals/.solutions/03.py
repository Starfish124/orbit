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


def run(cases, system, grader):
    results = []
    passes = 0
    for case in cases:
        try:
            output = system(case["input"])
        except Exception as e:
            output = None
            passed = False
            reason = "error: %s: %s" % (type(e).__name__, e)
        else:
            passed, reason = grader(output, case["expected"])
        if passed:
            passes += 1
        results.append({"id": case["id"], "output": output, "pass": passed, "reason": reason})
    if results:
        pass_rate = passes / len(results)
    else:
        pass_rate = 0.0
    return {"results": results, "pass_rate": pass_rate}
