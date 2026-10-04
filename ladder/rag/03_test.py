import math

import rag

assert hasattr(rag, "cosine"), "no function called cosine yet"
assert hasattr(rag, "top_k"), "no function called top_k yet"
assert rag.tokenize("A-b") == ["a", "b"], "tokenize from stage 2 broke"
got = rag.cosine({"a": 1.0, "b": 2.0}, {"a": 3.0, "c": 4.0})
want = 3 / (math.sqrt(5) * 5)
assert abs(got - want) < 1e-9, "cosine({'a': 1, 'b': 2}, {'a': 3, 'c': 4}) = 3 / (sqrt(5) * 5) = %.6f, got %r" % (want, got)
assert abs(rag.cosine({"x": 2.0}, {"x": 7.0}) - 1.0) < 1e-9, "same direction should give 1.0 whatever the lengths"
assert rag.cosine({"x": 1.0}, {"y": 1.0}) == 0.0, "no shared terms should give 0.0"
assert rag.cosine({}, {"y": 1.0}) == 0.0, "an empty vector has no direction: cosine should be 0.0, not a ZeroDivisionError"
got = rag.top_k({"b": 0.5, "a": 0.9, "c": 0.5, "d": 0.0, "e": 0.7}, 3)
assert got == [("a", 0.9), ("e", 0.7), ("b", 0.5)], "top_k: highest score first, ties by id (b before c). Expected [('a', 0.9), ('e', 0.7), ('b', 0.5)], got %r" % (got,)
got = rag.top_k({"b": 0.5, "a": 0.9, "c": 0.5, "d": 0.0}, 10)
assert got == [("a", 0.9), ("b", 0.5), ("c", 0.5)], "a score of 0 is not a hit and is left out; k bigger than the hits returns them all. Got %r" % (got,)
assert rag.top_k({}, 3) == [], "top_k of no scores should be []"
# the whole search, by hand
chunks = {"pets#0": "my dog chases the cat", "pets#1": "the cat sleeps all day", "cars#0": "the car needs oil"}
tokens = {i: rag.tokenize(t) for i, t in chunks.items()}
idf = rag.idf_table(list(tokens.values()))
vecs = {i: rag.tfidf(t, idf) for i, t in tokens.items()}
q = rag.tfidf(rag.tokenize("the cat sleeps"), idf)
hits = rag.top_k({i: rag.cosine(q, v) for i, v in vecs.items()}, 2)
assert [i for i, _ in hits] == ["pets#1", "pets#0"], "searching 'the cat sleeps' should rank pets#1 then pets#0, got %r" % (hits,)
