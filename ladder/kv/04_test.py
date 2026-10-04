import kv

assert callable(getattr(kv, "count", None)), "no function called count yet"
assert callable(getattr(kv, "find", None)), "no function called find yet"
start = kv.count()
kv.put("x", "red")
assert kv.count() == start + 1, "count should go up by 1 after putting a new key"
kv.put("x", "red")
assert kv.count() == start + 1, "overwriting a key should not change count"
kv.put("b", "red")
kv.put("a", "red")
kv.put("c", "blue")
assert kv.find("red") == ["a", "b", "x"], "find('red') should be ['a', 'b', 'x'] (sorted), got %r" % (kv.find("red"),)
assert kv.find("green") == [], "find of a value nobody holds should be [], got %r" % (kv.find("green"),)
kv.delete("x")
assert kv.find("red") == ["a", "b"], "a deleted key should not be found"
