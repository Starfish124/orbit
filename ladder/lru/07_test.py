import lru
from _speed import check_speed

assert "OrderedDict" not in open(lru.__file__).read(), "stage 6 rule still holds: no OrderedDict"
gone = []
c = lru.LRU(2, on_evict=lambda k, v: gone.append((k, v)))
c.put("a", 1); c.put("b", 2); c.put("a", 10)
assert gone == [], "overwriting is not evicting: on_evict should not be called yet, got %r" % (gone,)
c.put("c", 3)
c.get("a")
c.put("d", 4)
assert gone == [("b", 2), ("c", 3)], "on_evict should get (key, value) of each evicted key in order, got %r" % (gone,)
plain = lru.LRU(1)
plain.put("x", 1); plain.put("y", 2)
assert plain.get("y") == 2, "LRU(1) with no on_evict should still evict without crashing"
check_speed()
