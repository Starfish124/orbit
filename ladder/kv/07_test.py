import kv

s = kv.KV()
s.put("a", 1)
s.begin()
s.put("a", 2)
s.begin()
s.put("a", 3)
s.rollback()
assert s.get("a") == 2, "inner rollback should go back to 2 (the outer transaction's value), got %r" % (s.get("a"),)
s.rollback()
assert s.get("a") == 1, "outer rollback should go back to 1, got %r" % (s.get("a"),)
s.begin()
s.put("b", 1)
s.begin()
s.put("b", 2)
s.commit()
assert s.get("b") == 2, "inner commit should keep b = 2"
s.rollback()
assert s.get("b") is None, "outer rollback should undo the inner committed change too"
try:
    s.rollback()
except RuntimeError:
    pass
else:
    raise AssertionError("every transaction is closed now: rollback() should raise RuntimeError")
