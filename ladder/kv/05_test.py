import kv

assert hasattr(kv, "KV"), "no class called KV yet"
a = kv.KV()
b = kv.KV()
a.put("k", 1)
assert a.get("k") == 1, "put/get on a KV object should work"
assert b.get("k") is None, "two KV objects share data: create the dict in __init__ with self.data = {}"
assert a.get("missing") is None, "get of a missing key should return None"
assert a.count() == 1 and b.count() == 0, "count should only count this object's keys"
a.put("j", 1)
assert a.find(1) == ["j", "k"], "find should return sorted keys, got %r" % (a.find(1),)
assert a.delete("k") is True and a.delete("k") is False, "delete: True, then False"
assert a.count() == 1, "count after delete should be 1"
