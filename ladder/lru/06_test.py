import lru
from _speed import check_speed

src = open(lru.__file__).read()
assert "OrderedDict" not in src, "the word OrderedDict is still in your file: build the linked list yourself"
assert "move_to_end" not in src and "popitem" not in src, "no OrderedDict methods either: move nodes yourself"
c = lru.LRU(3)
for k in "abc":
    c.put(k, k.upper())
c.get("a")
c.put("b", "B2")
c.put("d", "D")
assert c.get("c") is None, "'c' was least recently used and should be evicted"
assert [c.get(k) for k in "abd"] == ["A", "B2", "D"], "a, b, d should survive with their latest values"
c.put("e", "E")
assert c.get("a") is None, "after gets of a, b, d in that order, 'a' is least recent and should go"
assert c.size() == 3, "size should stay 3"
one = lru.LRU(1)
one.put("x", 1); one.put("x", 2); one.put("y", 3)
assert one.get("x") is None and one.get("y") == 3 and one.size() == 1, "capacity 1 is the edge case that breaks sentinel code"
assert c.stats()["evictions"] == 2, "stats should still count evictions, got %r" % (c.stats(),)
check_speed()
