import kv

s = kv.KV()
s.put("a", 1)
s.put("b", 2)
for m in ("begin", "rollback", "commit"):
    assert callable(getattr(s, m, None)), "KV has no %s() method yet" % m
s.begin()
s.put("a", 100)
s.delete("b")
s.put("c", 3)
assert s.get("a") == 100, "inside a transaction, get should see the new value"
s.rollback()
assert s.get("a") == 1, "rollback should restore 'a' to 1, got %r (snapshot = same dict? copy it)" % (s.get("a"),)
assert s.get("b") == 2, "rollback should bring back the deleted key 'b'"
assert s.get("c") is None, "rollback should remove 'c', which was added in the transaction"
s.begin()
s.put("a", 5)
s.commit()
assert s.get("a") == 5, "after commit the change should stay"
for m in ("rollback", "commit"):
    try:
        getattr(s, m)()
    except RuntimeError:
        pass
    else:
        raise AssertionError("%s() with no transaction open should raise RuntimeError" % m)
