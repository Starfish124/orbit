import math

import rag

for name in ("tokenize", "term_counts", "idf_table", "tfidf"):
    assert hasattr(rag, name), "no function called %s yet" % name
assert rag.chunk("d", "a b c", 2, 1) == [("d#0", "a b"), ("d#1", "b c")], "chunk from stage 1 broke"
got = rag.tokenize("Hello, World! It's 2026.")
assert got == ["hello", "world", "it", "s", "2026"], "tokenize: lowercase, every non-letter/digit is a break. Expected ['hello', 'world', 'it', 's', '2026'], got %r" % (got,)
assert rag.tokenize("") == [] and rag.tokenize("?!") == [], "tokenize of no words should be []"
assert rag.tokenize("café naïve") == ["café", "naïve"], "accented letters are letters too, got %r" % (rag.tokenize("café naïve"),)
got = rag.term_counts(["a", "b", "a"])
assert got == {"a": 2, "b": 1}, "term_counts(['a', 'b', 'a']) should be {'a': 2, 'b': 1}, got %r" % (got,)
assert rag.term_counts([]) == {}, "term_counts([]) should be {}"
docs = [["cat", "sat"], ["cat", "cat", "ran"], ["dog"]]
idf = rag.idf_table(docs)
assert set(idf) == {"cat", "sat", "ran", "dog"}, "idf_table needs one entry per term seen, got keys %r" % (sorted(idf),)
want = math.log(4 / 3) + 1
assert abs(idf["cat"] - want) < 1e-9, "cat is in 2 of 3 docs: idf = ln((3+1)/(2+1)) + 1 = %.6f, got %r (count a doc once even if the word repeats)" % (want, idf["cat"])
want = math.log(4 / 2) + 1
assert abs(idf["dog"] - want) < 1e-9, "dog is in 1 of 3 docs: idf = ln(4/2) + 1 = %.6f, got %r" % (want, idf["dog"])
assert idf["dog"] > idf["cat"], "a rarer word must weigh more"
vec = rag.tfidf(["cat", "cat", "ran", "zebra"], idf)
assert set(vec) == {"cat", "ran"}, "tfidf skips words the idf table doesn't know (zebra): expected keys cat, ran, got %r" % (sorted(vec),)
assert abs(vec["cat"] - 2 * idf["cat"]) < 1e-9, "tfidf weight = count * idf: cat appears twice, expected %.6f, got %r" % (2 * idf["cat"], vec["cat"])
assert rag.tfidf([], idf) == {}, "tfidf of no tokens should be {}"
