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
