import json


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
