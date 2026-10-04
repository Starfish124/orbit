"""Every stage's checks. Stage N's test runs check1..checkN, so earlier stages stay honest."""
import inspect

import agent
from _fakes import FakeClock, FakeModel


def add(a, b):
    return a + b


def divide(a, b):
    return a / b


def shout(text):
    return text.upper()


def takes(fn, *names):
    params = inspect.signature(fn).parameters
    for name in names:
        assert name in params, "%s() should accept an argument called %s" % (fn.__name__, name)


def check_shape(calls):
    for call in calls:
        assert isinstance(call, list), "run() should send the model a list of messages"
        for m in call:
            assert set(m) == {"role", "content"}, \
                "every message is a dict with exactly the keys 'role' and 'content', got %r" % (m,)
            assert isinstance(m["content"], str), \
                "every message content should be a string (the model reads text), got %r" % (m,)


def check1():
    for f in ("register", "tools_prompt"):
        assert callable(getattr(agent, f, None)), "no function called %s yet" % f
    agent.register("add", add, "adds two numbers a and b")
    agent.register("shout", shout, "returns the text in capitals")
    got = agent.tools_prompt()
    assert isinstance(got, str), "tools_prompt() should return one string, got %r" % (got,)
    lines = got.split("\n")
    for line in ("add: adds two numbers a and b", "shout: returns the text in capitals"):
        assert line in lines, "tools_prompt() should have the line %r, got %r" % (line, got)
    assert lines.index("add: adds two numbers a and b") < lines.index("shout: returns the text in capitals"), \
        "tools should be listed in the order they were registered, got %r" % got
    agent.register("add", add, "adds a and b")
    lines = agent.tools_prompt().split("\n")
    assert "add: adds a and b" in lines, "registering 'add' again should replace its description, got %r" % lines
    assert len([x for x in lines if x.startswith("add:")]) == 1, \
        "registering 'add' twice should still list it once, got %r" % lines
    agent.register("divide", divide, "divides a by b")


def check2():
    assert callable(getattr(agent, "call_tool", None)), "no function called call_tool yet"
    got = agent.call_tool("add", {"a": 2, "b": 3})
    assert got == "5", "call_tool('add', {'a': 2, 'b': 3}) should return the STRING '5' (results go back to the model as text), got %r" % (got,)
    got = agent.call_tool("shout", {"text": "hi"})
    assert got == "HI", "call_tool('shout', {'text': 'hi'}) should return 'HI', got %r" % (got,)
    cases = [
        ("nope", {}, "an unknown tool", "nope"),
        ("add", {"a": 1}, "a missing argument", ""),
        ("add", {"a": 1, "b": 2, "c": 3}, "an extra argument", ""),
        ("add", None, "args that are not a dict", ""),
        ("divide", {"a": 1, "b": 0}, "an exception inside the tool", "division by zero"),
    ]
    for name, args, what, must in cases:
        try:
            got = agent.call_tool(name, args)
        except Exception as e:
            raise AssertionError("call_tool(%r, %r) crashed with %s: %s. %s should come back as a string "
                                 "starting 'error:', never a crash" % (name, args, type(e).__name__, e, what))
        assert isinstance(got, str) and got.startswith("error:"), \
            "call_tool(%r, %r): %s should return a string starting 'error:', got %r" % (name, args, what, got)
        assert must in got, "the error for %s should mention %r so the model can fix it, got %r" % (what, must, got)


def check3():
    assert callable(getattr(agent, "run", None)), "no function called run yet"
    fake = FakeModel([{"tool": "add", "args": {"a": 2, "b": 3}}, {"final": "2 + 3 = 5"}])
    got = agent.run("what is 2 + 3?", fake)
    assert got == "2 + 3 = 5", "run() should return the text of the final reply, got %r" % (got,)
    assert len(fake.seen) == 2, "one tool call then a final: the model should be called 2 times, got %d" % len(fake.seen)
    check_shape(fake.seen)
    first, second = fake.seen
    assert len(first) == 2, "the first call should get 2 messages (system, task), got %r" % (first,)
    assert first[0]["role"] == "system", "message 0 should have role 'system', got %r" % (first[0],)
    assert agent.tools_prompt() in first[0]["content"], \
        "the system message should contain tools_prompt() so the model knows its tools, got %r" % first[0]["content"]
    assert first[1] == {"role": "user", "content": "what is 2 + 3?"}, \
        "message 1 should be {'role': 'user', 'content': <the task>}, got %r" % (first[1],)
    assert len(second) == 4 and second[:2] == first, \
        "the second call should get the same 2 messages plus 2 new ones, got %r" % (second,)
    assert second[2]["role"] == "assistant", "message 2 should be the model's own reply, role 'assistant', got %r" % (second[2],)
    assert second[3] == {"role": "tool", "content": "5"}, \
        "message 3 should be {'role': 'tool', 'content': '5'} (the tool's result), got %r" % (second[3],)

    fake = FakeModel([{"tool": "divide", "args": {"a": 1, "b": 0}}, {"tool": "nope", "args": {}}, {"final": "gave up"}])
    got = agent.run("divide 1 by 0", fake)
    assert got == "gave up", "a failing tool must not end the run: the error goes back to the model, got %r" % (got,)
    assert fake.seen[1][-1]["role"] == "tool" and "division by zero" in fake.seen[1][-1]["content"], \
        "after a crashing tool the model should see the error as a tool message, last message was %r" % (fake.seen[1][-1],)
    assert fake.seen[2][-1]["content"].startswith("error:"), \
        "after an unknown tool the model should see an 'error:' tool message, got %r" % (fake.seen[2][-1],)

    fake = FakeModel([{"final": "hi"}])
    got = agent.run("say hi", fake)
    assert got == "hi" and len(fake.seen) == 1, "a model that answers at once: one call, answer 'hi', got %r" % (got,)


def check4():
    takes(agent.run, "max_steps")
    fake = FakeModel([], forever={"tool": "add", "args": {"a": 1, "b": 1}})
    got = agent.run("loop", fake, max_steps=5)
    assert len(fake.seen) == 5, "max_steps=5 means at most 5 model calls, got %d" % len(fake.seen)
    assert isinstance(got, str) and got.startswith("stopped:") and "5" in got, \
        "hitting the limit should return a string starting 'stopped:' that says the limit (5), got %r" % (got,)
    fake = FakeModel([], forever={"tool": "add", "args": {"a": 1, "b": 1}})
    agent.run("loop", fake)
    assert len(fake.seen) == 10, "without max_steps the limit should be 10 model calls, got %d" % len(fake.seen)
    call = {"tool": "add", "args": {"a": 1, "b": 1}}
    fake = FakeModel([call, call, {"final": "just in time"}])
    got = agent.run("close call", fake, max_steps=3)
    assert got == "just in time", "a final on the last allowed step still counts, got %r" % (got,)


def check5():
    assert callable(getattr(agent, "parse_reply", None)), "no function called parse_reply yet"
    good = [
        ('{"final": "42"}', {"final": "42"}),
        ('Sure! I will add them.\n{"tool": "add", "args": {"a": 2, "b": 3}}\nHope that helps.',
         {"tool": "add", "args": {"a": 2, "b": 3}}),
        ('```json\n{"tool": "add", "args": {"a": 2, "b": 3}}\n```', {"tool": "add", "args": {"a": 2, "b": 3}}),
        ('Calling: {"tool": "save", "args": {"data": {"x": 1}}}', {"tool": "save", "args": {"data": {"x": 1}}}),
    ]
    for text, want in good:
        try:
            got = agent.parse_reply(text)
        except Exception as e:
            raise AssertionError("parse_reply(%r) crashed with %s: %s, it should return %r" % (text, type(e).__name__, e, want))
        assert got == want, "parse_reply(%r) should return %r, got %r" % (text, want, got)
    bad = [
        ("The answer is 42.", "text with no JSON in it"),
        ('{"tool": "add", "args": {a: 2}}', "broken JSON (keys need double quotes)"),
        ('{"note": "hi"}', "JSON with neither a 'tool' nor a 'final' key"),
        ("", "an empty reply"),
    ]
    for text, what in bad:
        try:
            got = agent.parse_reply(text)
        except ValueError:
            continue
        except Exception as e:
            raise AssertionError("parse_reply(%r), %s: raised %s, it should raise ValueError" % (text, what, type(e).__name__))
        raise AssertionError("parse_reply(%r), %s: should raise ValueError, returned %r" % (text, what, got))

    said = 'Let me add those.\n```json\n{"tool": "add", "args": {"a": 2, "b": 3}}\n```'
    fake = FakeModel([said, "{tool: add, oops", 'Done! {"final": "5"}'])
    got = agent.run("add 2 and 3", fake)
    assert got == "5", "run() should read text replies with parse_reply and return '5', got %r" % (got,)
    check_shape(fake.seen)
    assert fake.seen[1][-2] == {"role": "assistant", "content": said}, \
        "a text reply should go into messages exactly as the model wrote it, got %r" % (fake.seen[1][-2],)
    assert fake.seen[1][-1] == {"role": "tool", "content": "5"}, \
        "the tool call inside the text should run, last message was %r" % (fake.seen[1][-1],)
    last = fake.seen[2][-1]
    assert last["role"] == "user" and last["content"].startswith("error:"), \
        "after an unreadable reply the model should get a 'user' message starting 'error:' and a new try, got %r" % (last,)
    fake = FakeModel([], forever="I think... hmm")
    got = agent.run("never clear", fake, max_steps=4)
    assert len(fake.seen) == 4 and got.startswith("stopped:"), \
        "unreadable replies still count as steps: 4 calls then 'stopped:', got %d calls and %r" % (len(fake.seen), got)


def check6():
    takes(agent.run, "clock", "count_tokens")
    assert isinstance(getattr(agent, "last_run", None), dict), "no dict called last_run yet"
    clock = FakeClock()

    def slow_add(a, b):
        clock.now += 3
        return a + b

    agent.register("slow_add", slow_add, "adds a and b, slowly")
    fake = FakeModel([{"tool": "slow_add", "args": {"a": 2, "b": 3}}, "not json at all", {"final": "5"}],
                     clock=clock, seconds=2)
    got = agent.run("add slowly", fake, clock=clock, count_tokens=len)
    assert got == "5", "run() should still return the answer, got %r" % (got,)
    trace = agent.last_run.get("trace")
    assert isinstance(trace, list) and len(trace) == 3, \
        "last_run['trace'] should be a list with one entry per model call (3), got %r" % (trace,)
    want = [
        {"step": 1, "tool": "slow_add", "args": {"a": 2, "b": 3}, "result": "5", "seconds": 5},
        {"step": 2, "tool": None, "args": None, "seconds": 2},
        {"step": 3, "tool": None, "args": None, "result": "5", "seconds": 2},
    ]
    for entry, w in zip(trace, want):
        for key in w:
            assert entry.get(key) == w[key], \
                "trace step %d: %r should be %r, got %r (whole entry %r)" % (w["step"], key, w[key], entry.get(key), entry)
    assert str(trace[1].get("result", "")).startswith("error:"), \
        "trace step 2 (unreadable reply): result should be the 'error:' message, got %r" % (trace[1].get("result"),)
    total = 0
    for i, entry in enumerate(trace):
        sent = sum(len(m["content"]) for m in fake.seen[i])
        assert entry.get("tokens") == sent, \
            "trace step %d: tokens should be count_tokens summed over every message sent in that call (%d), got %r" % (i + 1, sent, entry.get("tokens"))
        total += sent
    assert agent.last_run.get("tokens") == total, \
        "last_run['tokens'] should be the total over all calls (%d): every call pays for the whole history, got %r" % (total, agent.last_run.get("tokens"))
    agent.run("again", FakeModel([{"final": "hi"}]), clock=clock, count_tokens=len)
    assert len(agent.last_run["trace"]) == 1, "each run() should start a fresh trace, got %r" % (agent.last_run["trace"],)
    got = agent.run("defaults", FakeModel([{"final": "ok"}]))
    assert got == "ok" and agent.last_run["tokens"] > 0, \
        "without clock/count_tokens run() should use real time and count words, tokens was %r" % (agent.last_run["tokens"],)


def check7():
    takes(agent.run, "approve")
    takes(agent.register, "dangerous")
    ran = []

    def delete_file(path):
        ran.append(path)
        return "deleted " + path

    agent.register("delete_file", delete_file, "deletes a file", dangerous=True)
    asked = []

    def say_no(tool, args):
        asked.append((tool, args))
        return False

    fake = FakeModel([{"tool": "delete_file", "args": {"path": "/important"}},
                      {"tool": "add", "args": {"a": 1, "b": 1}}, {"final": "ok"}])
    got = agent.run("clean up", fake, approve=say_no)
    assert ran == [], "approve said no, but delete_file ran anyway on %r" % ran
    assert asked == [("delete_file", {"path": "/important"})], \
        "approve should be asked once, as approve('delete_file', {'path': '/important'}), and never for safe tools; calls were %r" % asked
    msg = fake.seen[1][-1]
    assert msg["role"] == "tool" and msg["content"].startswith("denied"), \
        "the model should be told with a tool message starting 'denied', got %r" % (msg,)
    assert fake.seen[2][-1]["content"] == "2" and got == "ok", "after a denial the run goes on normally"

    fake = FakeModel([{"tool": "delete_file", "args": {"path": "/tmp/x"}}, {"final": "done"}])
    agent.run("clean tmp", fake, approve=lambda tool, args: True)
    assert ran == ["/tmp/x"], "approve said yes: delete_file should run once on '/tmp/x', ran %r" % ran
    assert fake.seen[1][-1]["content"] == "deleted /tmp/x", "an approved tool's result goes back as usual, got %r" % (fake.seen[1][-1],)

    fake = FakeModel([{"tool": "delete_file", "args": {"path": "/etc"}}, {"final": "done"}])
    agent.run("no human around", fake)
    assert ran == ["/tmp/x"], "no approve function at all means nobody said yes: a dangerous tool must not run, ran %r" % ran
    assert fake.seen[1][-1]["content"].startswith("denied"), "and the model is told 'denied', got %r" % (fake.seen[1][-1],)


def check8():
    takes(agent.run, "budget")

    def read(n):
        return ("line %d of a long file. " % n) * 8

    agent.register("read", read, "reads part n of a long file")
    task = "summarise the file"
    probe = FakeModel([{"final": "x"}])
    agent.run(task, probe, count_tokens=len)
    system = probe.seen[0][0]
    base = sum(len(m["content"]) for m in probe.seen[0])
    budget = base + 700
    script = [{"tool": "read", "args": {"n": i}} for i in range(1, 7)] + [{"final": "a long file"}]

    fake = FakeModel(list(script))
    got = agent.run(task, fake, count_tokens=len, budget=budget)
    assert got == "a long file", "run() should still finish, got %r" % (got,)
    check_shape(fake.seen)
    for i, call in enumerate(fake.seen):
        size = sum(len(m["content"]) for m in call)
        assert size <= budget, "call %d sent %d tokens, over the budget of %d: shorten older messages first" % (i + 1, size, budget)
        assert call[0] == system, "call %d: the system prompt must never be shortened, got %r" % (i + 1, call[0])
        assert call[1] == {"role": "user", "content": task}, "call %d: the task must never be shortened, got %r" % (i + 1, call[1])
        if i > 0:
            assert call[-1] == {"role": "tool", "content": read(i)}, \
                "call %d: the newest message (the result the model just asked for) must arrive whole, got %r" % (i + 1, call[-1])

    fake = FakeModel(list(script))
    agent.run(task, fake, count_tokens=len, budget=base + 100)
    for i, call in enumerate(fake.seen):
        assert call[0] == system and call[1] == {"role": "user", "content": task}, \
            "a budget too small to meet: still never touch the system prompt or the task, call %d got %r" % (i + 1, call[:2])
        if i > 0:
            assert call[-1] == {"role": "tool", "content": read(i)}, \
                "a budget too small to meet: the newest message still arrives whole, call %d got %r" % (i + 1, call[-1])

    plain, roomy = FakeModel(list(script)), FakeModel(list(script))
    agent.run(task, plain, count_tokens=len)
    agent.run(task, roomy, count_tokens=len, budget=10 ** 9)
    assert roomy.seen == plain.seen, "under the budget nothing should change: same messages as with no budget at all"


CHECKS = [check1, check2, check3, check4, check5, check6, check7, check8]


def run_up_to(n):
    for check in CHECKS[:n]:
        check()
