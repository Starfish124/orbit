import math

import rag

assert hasattr(rag, "bm25"), "no function called bm25 yet"
assert rag.top_k({"a": 1.0, "b": 2.0}, 1) == [("b", 2.0)], "top_k from stage 3 broke"
docs = {"x": ["cat", "sat"], "y": ["cat", "cat", "ran", "far"], "z": ["dog"]}
got = rag.bm25(["cat"], docs)
assert set(got) == {"x", "y", "z"}, "bm25 returns a score for EVERY doc id, got keys %r" % (sorted(got),)
assert got["z"] == 0.0, "z has no 'cat': its score should be 0.0, got %r" % (got["z"],)
idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
avgdl = 7 / 3
want_x = idf * 1 * 2.5 / (1 + 1.5 * (1 - 0.75 + 0.75 * 2 / avgdl))
want_y = idf * 2 * 2.5 / (2 + 1.5 * (1 - 0.75 + 0.75 * 4 / avgdl))
assert abs(got["x"] - want_x) < 1e-9, "bm25(['cat'])['x'] should be %.6f, got %r (check idf, avgdl and the length part)" % (want_x, got["x"])
assert abs(got["y"] - want_y) < 1e-9, "bm25(['cat'])['y'] should be %.6f, got %r" % (want_y, got["y"])
got2 = rag.bm25(["cat", "cat", "unknownword"], docs)
assert abs(got2["x"] - want_x) < 1e-9, "each DISTINCT query term counts once, and unknown terms add nothing: expected %.6f, got %r" % (want_x, got2["x"])
got3 = rag.bm25(["cat"], docs, k1=1.2, b=0.0)
want = idf * 2 * 2.2 / (2 + 1.2)
assert abs(got3["y"] - want) < 1e-9, "k1 and b are keyword arguments: with k1=1.2, b=0 doc y should be %.6f, got %r" % (want, got3["y"])
assert rag.bm25(["cat"], {}) == {}, "no docs, no scores: {}"
assert rag.bm25(["cat"], {"e": []}) == {"e": 0.0}, "only empty docs: every score is 0.0 (and no ZeroDivisionError)"
# where the two disagree: a short doc that shares one word vs a long doc that covers the question
texts = {"guide": "what a home solar system will cost you depends on roof size, sun hours, the installer, local permits, wiring, the inverter and the batteries",
         "eclipse": "solar eclipse tonight",
         "cake": "chocolate cake recipe with butter and sugar",
         "bus": "bus timetable for the city centre"}
toks = {i: rag.tokenize(t) for i, t in texts.items()}
table = rag.idf_table(list(toks.values()))
q = rag.tokenize("solar cost")
qv = rag.tfidf(q, table)
cos = rag.top_k({i: rag.cosine(qv, rag.tfidf(t, table)) for i, t in toks.items()}, 2)
bm = rag.top_k(rag.bm25(q, toks), 2)
assert [i for i, _ in cos] == ["eclipse", "guide"], "TF-IDF cosine should (wrongly) rank the short 'eclipse' doc first for 'solar cost', got %r" % (cos,)
assert [i for i, _ in bm] == ["guide", "eclipse"], "BM25 should rank the long 'guide' first for 'solar cost': it matches both words. Got %r" % (bm,)
