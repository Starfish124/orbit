import lru

c = lru.LRU(2)
c.put("a", 1)
c.put("b", 2)
c.put("a", 10)
assert c.size() == 2, "overwriting 'a' should not change size"
assert c.get("a") == 10, "put of an existing key should replace its value"
c.put("c", 3)
assert c.get("b") is None, "put('a', ...) again made 'a' recent, so 'b' should be evicted"
assert c.get("a") == 10 and c.get("c") == 3
for i in range(20):
    c.put("c", i)
assert c.size() == 2, "20 overwrites of one key should leave size at 2"
c.put("x", 1)
c.put("y", 2)
assert c.get("x") == 1 and c.get("y") == 2 and c.size() == 2, "a key listed twice in your order breaks eviction here"
