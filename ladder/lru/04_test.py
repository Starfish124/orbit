import lru

c = lru.LRU(2)
assert callable(getattr(c, "stats", None)), "no stats() method yet"
assert c.stats() == {"hits": 0, "misses": 0, "evictions": 0}, "a new cache should report all zeros, got %r" % (c.stats(),)
c.put("a", 1)
c.put("b", 2)
c.get("a")
c.get("zz")
c.put("c", 3)
c.put("c", 4)
c.get("b")
c.get("c")
want = {"hits": 2, "misses": 2, "evictions": 1}
assert c.stats() == want, "expected %r, got %r (put never counts as a hit or miss; overwriting is not an eviction)" % (want, c.stats())
