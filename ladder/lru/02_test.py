import lru

c = lru.LRU(2)
c.put("a", 1)
c.put("b", 2)
assert c.get("a") == 1
c.put("c", 3)
assert c.get("b") is None, "get('a') made 'a' recent, so 'b' was least recently used and should be gone"
assert c.get("a") == 1, "'a' was used recently and should survive"
assert c.get("c") == 3
c.get("nope")
c.put("d", 4)
assert c.get("a") is None, "after get('a'), get('c'), a miss, then put('d'): 'a' is least recently used and should be gone"
assert c.size() == 2
