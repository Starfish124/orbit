import kv

kv.put("a", 1)
assert kv.get("a") == 1, "put/get from stage 2 broke"
try:
    missing = kv.get("does-not-exist")
except KeyError:
    raise AssertionError("get of a missing key crashed with KeyError; it should return None")
assert missing is None, "get of a missing key should return None, got %r" % (missing,)
assert callable(getattr(kv, "delete", None)), "no function called delete yet"
assert kv.delete("a") is True, "deleting a key that exists should return True"
assert kv.get("a") is None, "after delete('a'), get('a') should be None"
assert kv.delete("a") is False, "deleting it a second time should return False, not crash"
