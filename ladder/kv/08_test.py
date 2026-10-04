import kv

now = [1000]
s = kv.KV(clock=lambda: now[0])
s.put("forever", 1)
s.put("short", 2, ttl=10)
s.put("long", 2, ttl=50)
assert s.get("short") == 2, "a key with a ttl should be readable before it expires"
now[0] = 1009
assert s.get("short") == 2, "at 9 of 10 seconds the key should still be there"
now[0] = 1010
assert s.get("short") is None, "at exactly ttl seconds the key should be gone (now >= expiry)"
assert s.count() == 2, "count should skip expired keys: expected 2, got %r" % (s.count(),)
assert s.find(2) == ["long"], "find should skip expired keys, got %r" % (s.find(2),)
assert s.get("forever") == 1, "a key without ttl never expires"
s.put("long", 3)
now[0] = 5000
assert s.get("long") == 3, "putting a key again without ttl should clear its old expiry"
s.begin()
s.put("t", 1, ttl=5)
s.rollback()
assert s.get("t") is None, "rollback should still work with ttl keys"
assert kv.KV().put("x", 1) is None, "KV() with no clock argument should use the real clock"
