tools = {}


def register(name, fn, description):
    tools[name] = {"fn": fn, "description": description}


def tools_prompt():
    lines = []
    for name in tools:
        lines.append(name + ": " + tools[name]["description"])
    return "\n".join(lines)
