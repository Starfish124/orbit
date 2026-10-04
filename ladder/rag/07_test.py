import rag

for name in ("recall_at_k", "reciprocal_rank", "evaluate"):
    assert hasattr(rag, name), "no function called %s yet" % name
assert rag.build_prompt("q", [], 100)[1] == [], "build_prompt from stage 6 broke"
ranked = ["a", "b", "c", "d"]
assert rag.recall_at_k(ranked, {"b", "d"}, 2) == 0.5, "recall@2: of {b, d} only b is in the top 2, so 0.5. Got %r" % (rag.recall_at_k(ranked, {"b", "d"}, 2),)
assert rag.recall_at_k(ranked, {"b", "d"}, 4) == 1.0, "recall@4 of {b, d} should be 1.0"
assert rag.recall_at_k(ranked, {"z"}, 4) == 0.0, "a relevant id never retrieved: recall 0.0"
assert rag.recall_at_k([], {"a"}, 3) == 0.0, "nothing retrieved: recall 0.0"
assert rag.reciprocal_rank(ranked, {"c", "d"}) == 1 / 3, "first relevant is c at position 3: 1/3. Got %r" % (rag.reciprocal_rank(ranked, {"c", "d"}),)
assert rag.reciprocal_rank(ranked, {"a"}) == 1.0, "relevant at position 1: 1.0 (positions start at 1)"
assert rag.reciprocal_rank(ranked, {"z"}) == 0.0, "no relevant found: 0.0"
calls = []
answers = {"q1": ["a#0", "b#0"], "q2": ["x#0", "c#0", "b#0"], "q3": []}


def fake_search(question, k):
    calls.append(k)
    return [(i, 1.0) for i in answers[question][:k]]


labeled = [("q1", {"a#0"}), ("q2", {"b#0", "c#0"}), ("q3", {"z#0"})]
got = rag.evaluate(fake_search, labeled, 2)
assert set(got) == {"recall", "mrr"}, "evaluate returns {'recall': ..., 'mrr': ...}, got %r" % (got,)
want_recall = (1.0 + 0.5 + 0.0) / 3
want_mrr = (1.0 + 0.5 + 0.0) / 3
assert abs(got["recall"] - want_recall) < 1e-9, "mean recall@2 should be %.4f, got %r" % (want_recall, got["recall"])
assert abs(got["mrr"] - want_mrr) < 1e-9, "MRR should be %.4f, got %r" % (want_mrr, got["mrr"])
assert calls == [2, 2, 2], "evaluate should call search(question, k) once per question, calls were %r" % (calls,)
try:
    rag.evaluate(fake_search, [], 2)
except ValueError:
    pass
else:
    raise AssertionError("evaluate with no labeled questions should raise ValueError (an average of nothing means nothing)")
# measure a real index: the number is the point, not a guess
idx = rag.Index(size=50, overlap=5)
idx.add_documents({"tea": "green tea is steeped at eighty degrees for three minutes",
                   "coffee": "espresso is pressed hot water through fine coffee grounds",
                   "juice": "fresh orange juice is squeezed from ripe oranges"})
got = rag.evaluate(idx.search, [("how hot for green tea", {"tea#0"}), ("orange juice", {"juice#0"}), ("making espresso", {"coffee#0"})], 1)
assert got == {"recall": 1.0, "mrr": 1.0}, "on this easy set BM25 finds every answer first: expected recall 1.0 and mrr 1.0, got %r" % (got,)
