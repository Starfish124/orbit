import lru
from _speed import check_speed

gone = []
c = lru.LRU(3, on_evict=lambda k, v: gone.append(k))
c.put("a", 1); c.put("b", 2); c.put("c", 3)
before = c.stats()
assert c.peek("a") == 1 and c.peek("zz") is None, "peek should return the value, or None when missing"
assert c.stats() == before, "peek must not change stats: %r became %r" % (before, c.stats())
c.put("d", 4)
assert gone == ["a"], "peek('a') must not make 'a' recent: 'a' should be evicted first, evicted: %r" % (gone,)
try:
    c.resize(0)
except ValueError:
    pass
else:
    raise AssertionError("resize(0) should raise ValueError")
c.get("b")
c.resize(1)
assert gone == ["a", "c", "d"], "resize(1) should evict c then d (b was just used), evicted so far: %r" % (gone,)
assert c.size() == 1 and c.get("b") == 2, "only 'b' should remain"
assert c.stats()["evictions"] == 3, "resize evictions count too: %r" % (c.stats(),)
c.resize(3)
c.put("x", 1); c.put("y", 2)
assert c.size() == 3 and gone == ["a", "c", "d"], "after growing to 3, three keys fit with no eviction"
assert "OrderedDict" not in open(lru.__file__).read(), "stage 6 rule still holds: no OrderedDict"
check_speed()
