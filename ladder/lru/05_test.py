import lru
from _speed import check_speed

# everything from stages 1-4 must still hold
c = lru.LRU(2)
c.put("a", 1); c.put("b", 2); c.get("a"); c.get("zz"); c.put("c", 3); c.put("c", 4)
assert c.get("b") is None and c.get("a") == 1 and c.get("c") == 4 and c.size() == 2, "LRU behaviour from stages 1-3 broke"
assert c.stats() == {"hits": 3, "misses": 2, "evictions": 1}, "stats from stage 4 broke: %r" % (c.stats(),)
check_speed()
