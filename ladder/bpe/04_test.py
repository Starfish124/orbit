import bpe

assert hasattr(bpe, "train"), "no function called train yet"
assert bpe.merge([5, 5, 5], (5, 5), 256) == [256, 5], "merge from stage 3 broke"
try:
    bpe.train("abc", 100)
except ValueError:
    pass
else:
    raise AssertionError("train(text, 100) should raise ValueError: the 256 byte ids are always in the vocabulary")
got = bpe.train("aaabdaaabac", 259)
want = {(97, 97): 256, (256, 97): 257, (257, 98): 258}
assert got == want, "train('aaabdaaabac', 259) should be %r, got %r" % (want, got)
assert list(got.values()) == [256, 257, 258], "merges must be stored in the order they were learned: %r" % (list(got.values()),)
got = bpe.train("cdcdabab", 257)
assert got == {(99, 100): 256}, ("'cd' and 'ab' both appear twice in 'cdcdabab': the tie goes to the pair "
                                 "that shows up FIRST, (99, 100). Got %r" % (got,))
got = bpe.train("aa", 300)
assert got == {(97, 97): 256}, "after merging 'aa' there are no pairs left: stop early, expected {(97, 97): 256}, got %r" % (got,)
assert bpe.train("", 300) == {}, "train('', 300) has nothing to merge: expected {}"
assert bpe.train("hello", 256) == {}, "vocab_size 256 means zero merges: expected {}"
