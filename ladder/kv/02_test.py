import kv

assert callable(getattr(kv, "put", None)), "no function called put yet"
assert callable(getattr(kv, "get", None)), "no function called get yet"
kv.put("a", 1)
assert kv.get("a") == 1, "after put('a', 1), get('a') should be 1, got %r" % (kv.get("a"),)
kv.put("a", 2)
assert kv.get("a") == 2, "putting the same key again should overwrite it"
kv.put("b", "hi")
assert kv.get("b") == "hi" and kv.get("a") == 2, "two keys should not disturb each other"
