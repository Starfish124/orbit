import bpe

assert hasattr(bpe, "get_stats"), "no function called get_stats yet"
assert bpe.to_bytes("é") == [195, 169], "to_bytes from stage 1 broke"
got = bpe.get_stats([1, 2, 3, 1, 2])
want = {(1, 2): 2, (2, 3): 1, (3, 1): 1}
assert got == want, "get_stats([1, 2, 3, 1, 2]) should be %r, got %r" % (want, got)
got = bpe.get_stats([5, 5, 5])
assert got == {(5, 5): 2}, "[5, 5, 5] has the pair (5, 5) at positions 0-1 AND 1-2: expected {(5, 5): 2}, got %r" % (got,)
assert bpe.get_stats([7]) == {}, "one id has no neighbours: get_stats([7]) should be {}, got %r" % (bpe.get_stats([7]),)
assert bpe.get_stats([]) == {}, "get_stats([]) should be {}"
ids = [1, 2, 3]
bpe.get_stats(ids)
assert ids == [1, 2, 3], "get_stats must not change the list it is given"
got = bpe.get_stats(bpe.to_bytes("aab"))
assert got == {(97, 97): 1, (97, 98): 1}, "get_stats(to_bytes('aab')) should be {(97, 97): 1, (97, 98): 1}, got %r" % (got,)
