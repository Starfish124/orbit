import rag

assert hasattr(rag, "Index"), "no class called Index yet"
assert rag.bm25(["a"], {"x": ["a"]})["x"] > 0, "bm25 from stage 4 broke"
idx = rag.Index(size=4, overlap=1)
for m in ("add_documents", "search", "text"):
    assert callable(getattr(idx, m, None)), "Index has no %s() method yet" % m
docs = {"pets": "the dog chases the cat and the cat runs up a tree",
        "cars": "change the oil in the car every year",
        "bake": "bread needs flour water salt and time"}
idx.add_documents(docs)
assert idx.text("pets#0") == "the dog chases the", "text('pets#0') should be 'the dog chases the' (size=4, overlap=1), got %r" % (idx.text("pets#0"),)
assert idx.text("cars#2") == "every year", "text('cars#2') should be 'every year', got %r" % (idx.text("cars#2"),)
hits = idx.search("up a tree", k=2)
assert isinstance(hits, list) and hits and hits[0][0] == "pets#3", "search('up a tree') should rank pets#3 first, got %r" % (hits,)
assert len(hits) == 2, "search(k=2) should return 2 hits, got %d" % len(hits)
want = rag.top_k(rag.bm25(rag.tokenize("up a tree"), {i: rag.tokenize(idx.text(i)) for i in ["pets#0", "pets#1", "pets#2", "pets#3", "cars#0", "cars#1", "cars#2", "bake#0", "bake#1"]}), 2)
assert hits == want, "search should be top_k over bm25 of every chunk: expected %r, got %r" % (want, hits)
assert idx.search("quantum", k=3) == [], "a query sharing no words should find nothing, got %r" % (idx.search("quantum", k=3),)
assert len(idx.search("the")) == 3, "k defaults to 3"
# incremental adds must give exactly the scores of building it all at once
one = rag.Index(size=4, overlap=1)
one.add_documents({"pets": docs["pets"]})
before = one.search("the oil", k=5)
one.add_documents({"cars": docs["cars"], "bake": docs["bake"]})
after = one.search("the oil", k=5)
fresh = rag.Index(size=4, overlap=1)
fresh.add_documents(docs)
assert after == fresh.search("the oil", k=5), "adding documents in two calls must score exactly like one call: expected %r, got %r (are idf or avgdl stale from the first add?)" % (fresh.search("the oil", k=5), after)
assert before != after, "adding documents must change the scores of later searches"
try:
    one.add_documents({"new": "brand new text", "cars": "again"})
except ValueError:
    pass
else:
    raise AssertionError("adding a doc id that is already indexed ('cars') should raise ValueError")
assert one.search("brand", k=1) == [], "when add_documents raises, nothing from that call may be added (check every id first)"
