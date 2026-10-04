import json

tools = {}


def register(name, fn, description):
    tools[name] = {"fn": fn, "description": description}


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


def run(task, model, max_steps=10):
    messages = [{"role": "system", "content": system_prompt()},
                {"role": "user", "content": task}]
    for step in range(max_steps):
        reply = model(messages)
        messages.append({"role": "assistant", "content": json.dumps(reply)})
        if "final" in reply:
            return reply["final"]
        result = call_tool(reply["tool"], reply.get("args", {}))
        messages.append({"role": "tool", "content": result})
    return "stopped: no final answer after %d steps" % max_steps
