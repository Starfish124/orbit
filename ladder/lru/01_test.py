import lru

assert hasattr(lru, "LRU"), "no class called LRU yet"
try:
    lru.LRU(0)
except ValueError:
    pass
else:
    raise AssertionError("LRU(0) should raise ValueError: a cache must hold at least 1 key")
c = lru.LRU(2)
c.put("a", 1)
c.put("b", 2)
assert c.get("a") == 1 and c.get("b") == 2, "put/get should work before the cache is full"
assert c.get("zzz") is None, "get of a missing key should return None"
assert c.size() == 2, "size() should be 2, got %r" % (c.size(),)
c.put("c", 3)
assert c.size() == 2, "the cache holds at most 2 keys: size() should stay 2, got %r" % (c.size(),)
assert c.get("a") is None, "'a' was put in first, so it should be thrown out when 'c' arrives"
assert c.get("b") == 2 and c.get("c") == 3, "'b' and 'c' should still be there"
