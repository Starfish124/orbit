import re

import rag

assert hasattr(rag, "build_prompt"), "no function called build_prompt yet"
assert callable(getattr(rag.Index(), "answer", None)), "Index has no answer() method yet"
passages = [("a#0", "Paris is the capital of France."), ("b#1", "France uses the euro.")]
prompt, used = rag.build_prompt("What is the capital?", passages, 1000)
want = ("Answer the question using only the sources below. Cite them like [1].\n\n"
        "[1] a#0\nParis is the capital of France.\n\n"
        "[2] b#1\nFrance uses the euro.\n\n"
        "Question: What is the capital?\nAnswer:")
assert prompt == want, "build_prompt should return exactly:\n%s\n--- got ---\n%s" % (want, prompt)
assert used == ["a#0", "b#1"], "used should list the chunk ids in the prompt, got %r" % (used,)
budget = len(want) - 1
prompt, used = rag.build_prompt("What is the capital?", passages, budget)
assert used == ["a#0"], "one char over budget: drop the LOWEST-ranked passage (the last), keep a#0. Got %r" % (used,)
assert len(prompt) <= budget and "[2]" not in prompt, "the prompt must fit the budget (%d chars), got %d" % (budget, len(prompt))
prompt, used = rag.build_prompt("What is the capital?", passages, 110)
assert used == [] and prompt.endswith("Question: What is the capital?\nAnswer:"), "if no passage fits, the prompt has no sources. Got %r" % (used,)
try:
    rag.build_prompt("What is the capital?", passages, 20)
except ValueError:
    pass
else:
    raise AssertionError("if even the question alone is over budget, raise ValueError")
idx = rag.Index(size=6, overlap=2)
idx.add_documents({"paris": "Paris is the capital of France and sits on the Seine river",
                   "euro": "France pays with the euro since 2002",
                   "pasta": "boil pasta in salted water for nine minutes"})
seen = []


def echo(prompt):
    seen.append(prompt)
    return "saw " + " ".join(re.findall(r"^\[\d+\] (\S+)$", prompt, re.M))


out = idx.answer("What river runs through Paris?", echo, k=2, min_score=0.5, budget=2000)
assert isinstance(out, dict) and set(out) == {"answer", "sources"}, "answer() returns a dict with exactly 'answer' and 'sources', got %r" % (out,)
assert len(seen) == 1, "the llm should be called exactly once, was called %d times" % len(seen)
hits = [i for i, _ in idx.search("What river runs through Paris?", k=2)]
assert out["sources"] == hits, "sources should be the retrieved chunk ids in rank order %r, got %r" % (hits, out["sources"])
assert out["answer"] == "saw " + " ".join(hits), "answer should be whatever the llm returned for the built prompt, got %r" % (out["answer"],)
assert "Question: What river runs through Paris?" in seen[0], "the llm must be given the prompt from build_prompt"
small = idx.answer("What river runs through Paris?", echo, k=2, min_score=0.5, budget=len(seen[0]) - 1)
assert small["sources"] == hits[:1], "answer must pass budget to build_prompt and report only the sources that fit: expected %r, got %r" % (hits[:1], small["sources"])


def boom(prompt):
    raise AssertionError("the llm was called although retrieval found nothing good enough")


out = idx.answer("Everest height", boom, k=2, min_score=0.5)
assert out == {"answer": "I don't know", "sources": []}, "no hits: return {'answer': \"I don't know\", 'sources': []} without calling the llm, got %r" % (out,)
out = idx.answer("What river runs through Paris?", boom, k=2, min_score=1000)
assert out == {"answer": "I don't know", "sources": []}, "best score below min_score: say I don't know, don't call the llm. Got %r" % (out,)
