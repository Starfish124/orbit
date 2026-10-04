import rag
from _fakes import embed

assert hasattr(rag, "rrf"), "no function called rrf yet"
assert rag.reciprocal_rank(["a"], {"a"}) == 1.0, "reciprocal_rank from stage 7 broke"
got = rag.rrf([["a", "b"], ["b", "c"]])
want = {"a": 1 / 61, "b": 1 / 62 + 1 / 61, "c": 1 / 62}
assert set(got) == set(want) and all(abs(got[i] - want[i]) < 1e-12 for i in want), "rrf([['a','b'], ['b','c']]) with c=60 should be %r, got %r" % (want, got)
got = rag.rrf([["a"]], c=0)
assert abs(got["a"] - 1.0) < 1e-12, "rrf takes c as a keyword: rank 1 with c=0 scores 1/(0+1) = 1.0, got %r" % (got,)
assert rag.rrf([]) == {} and rag.rrf([[], []]) == {}, "no rankings, no scores"
plain = rag.Index(size=50, overlap=5)
try:
    plain.dense_search("dog", 3)
except ValueError:
    pass
else:
    raise AssertionError("dense_search on an Index made without embed should raise ValueError")
docs = {"pets": "how to train a puppy and keep your dog healthy",
        "cars": "check the engine oil in your car every month",
        "loans": "a bank loan or mortgage needs proof of income",
        "bread": "bake bread at home with flour yeast and an oven",
        "e42": "fault code e42 on the boiler means low water pressure",
        "storm": "storm warning with heavy rain in the forecast"}
idx = rag.Index(size=50, overlap=5, embed=embed)
idx.add_documents(docs)
got = idx.dense_search("canine care", 3)
assert got and got[0][0] == "pets#0", "dense_search('canine care') should find pets#0 through the embedding (no shared words!), got %r" % (got,)
assert idx.dense_search("fault e42", 3) == [], "the fake embedder can't see 'fault' or 'e42': dense_search finds nothing, got %r" % (idx.dense_search("fault e42", 3),)
labeled = [("canine care tips", {"pets#0"}),
           ("what does e42 mean", {"e42#0"}),
           ("automobile maintenance", {"cars#0"}),
           ("boiler pressure", {"e42#0"}),
           ("rain forecast", {"storm#0"}),
           ("sourdough recipe", {"bread#0"})]
lexical = rag.evaluate(idx.search, labeled, 3)
dense = rag.evaluate(idx.dense_search, labeled, 3)
hybrid = rag.evaluate(idx.hybrid_search, labeled, 3)
assert hybrid["mrr"] > lexical["mrr"] and hybrid["mrr"] > dense["mrr"], (
    "hybrid should beat both alone on MRR: bm25 %.2f, dense %.2f, hybrid %.2f" % (lexical["mrr"], dense["mrr"], hybrid["mrr"]))
assert hybrid == {"recall": 1.0, "mrr": 1.0}, "on this set hybrid should find every answer first, got %r" % (hybrid,)
bm = [i for i, _ in idx.search("dog loan", 6)]
dn = [i for i, _ in idx.dense_search("dog loan", 6)]
want = rag.top_k(rag.rrf([bm, dn]), 2)
assert idx.hybrid_search("dog loan", 2) == want, "hybrid_search = top_k(rrf([every bm25 hit, every dense hit])): expected %r, got %r" % (want, idx.hybrid_search("dog loan", 2))
