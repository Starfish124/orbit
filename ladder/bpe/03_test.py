import bpe

assert hasattr(bpe, "merge"), "no function called merge yet"
assert bpe.get_stats([5, 5, 5]) == {(5, 5): 2}, "get_stats from stage 2 broke"
got = bpe.merge([1, 2, 3, 1, 2], (1, 2), 256)
assert got == [256, 3, 256], "merge([1, 2, 3, 1, 2], (1, 2), 256) should be [256, 3, 256], got %r" % (got,)
got = bpe.merge([5, 5, 5], (5, 5), 256)
assert got == [256, 5], "merge([5, 5, 5], (5, 5), 256) should be [256, 5]: go left to right, a used id can't be used twice. Got %r" % (got,)
got = bpe.merge([5, 5, 5, 5], (5, 5), 256)
assert got == [256, 256], "merge([5, 5, 5, 5], (5, 5), 256) should be [256, 256], got %r" % (got,)
got = bpe.merge([1, 2, 1], (2, 9), 256)
assert got == [1, 2, 1], "a pair that is not there changes nothing, got %r" % (got,)
got = bpe.merge([2, 1], (1, 2), 256)
assert got == [2, 1], "(1, 2) is not in [2, 1]: order matters, got %r" % (got,)
assert bpe.merge([], (1, 2), 256) == [], "merge of [] should be []"
assert bpe.merge([1], (1, 2), 256) == [1], "merge([1], ...) should be [1]: a pair at the very end needs two ids"
ids = [1, 2]
bpe.merge(ids, (1, 2), 256)
assert ids == [1, 2], "merge must return a NEW list and leave the one it was given alone"
