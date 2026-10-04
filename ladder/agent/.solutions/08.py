import json
import time

tools = {}


def register(name, fn, description, dangerous=False):
    tools[name] = {"fn": fn, "description": description, "dangerous": dangerous}


def tools_prompt():
    lines = []
    for name in tools:
        lines.append(name + ": " + tools[name]["description"])
    return "\n".join(lines)


def call_tool(name, args):
    if name not in tools:
        return "error: there is no tool called " + str(name)
    try:
        result = tools[name]["fn"](**args)
    except Exception as e:
        return "error: " + type(e).__name__ + ": " + str(e)
    return str(result)


def system_prompt():
    return ("You are an agent. Reply with one JSON object.\n"
            'To use a tool: {"tool": "<name>", "args": {...}}\n'
            'To finish: {"final": "<your answer>"}\n'
            "Your tools:\n" + tools_prompt())


def parse_reply(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found in your reply")
    reply = json.loads(text[start:end + 1])   # bad JSON raises JSONDecodeError, a kind of ValueError
    if "tool" not in reply and "final" not in reply:
        raise ValueError('the JSON needs a "tool" or a "final" key')
    return reply


def count_words(text):
    return len(text.split())


def allowed(name, args, approve):
    if name not in tools or not tools[name]["dangerous"]:
        return True
    if approve is None:
        return False
    return approve(name, args)


def total_tokens(messages, count_tokens):
    total = 0
    for m in messages:
        total += count_tokens(m["content"])
    return total


def shrink(messages, budget, count_tokens):
    # messages[0] (system) and [1] (task) are never touched, nor the newest one
    i = 2
    while total_tokens(messages, count_tokens) > budget and i < len(messages) - 1:
        messages[i] = {"role": messages[i]["role"], "content": "[removed]"}
        i += 1


last_run = {"trace": [], "tokens": 0}


def run(task, model, max_steps=10, clock=time.monotonic, count_tokens=count_words, approve=None, budget=None):
    messages = [{"role": "system", "content": system_prompt()},
                {"role": "user", "content": task}]
    last_run["trace"] = []
    last_run["tokens"] = 0
    for step in range(1, max_steps + 1):
        if budget is not None:
            shrink(messages, budget, count_tokens)
        tokens = total_tokens(messages, count_tokens)
        last_run["tokens"] += tokens
        start = clock()
        reply = model(messages)
        entry = {"step": step, "tool": None, "args": None, "result": None, "tokens": tokens}
        last_run["trace"].append(entry)
        if isinstance(reply, str):
            messages.append({"role": "assistant", "content": reply})
            try:
                reply = parse_reply(reply)
            except ValueError as e:
                error = "error: " + str(e) + ". Reply with one JSON object."
                messages.append({"role": "user", "content": error})
                entry["result"] = error
                entry["seconds"] = clock() - start
                continue
        else:
            messages.append({"role": "assistant", "content": json.dumps(reply)})
        if "final" in reply:
            entry["result"] = reply["final"]
            entry["seconds"] = clock() - start
            return reply["final"]
        entry["tool"] = reply["tool"]
        entry["args"] = reply.get("args", {})
        if allowed(entry["tool"], entry["args"], approve):
            result = call_tool(entry["tool"], entry["args"])
        else:
            result = "denied: a human said no to " + entry["tool"] + ". Try another way."
        messages.append({"role": "tool", "content": result})
        entry["result"] = result
        entry["seconds"] = clock() - start
    return "stopped: no final answer after %d steps" % max_steps
