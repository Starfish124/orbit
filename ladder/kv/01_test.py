import kv

assert hasattr(kv, "db"), "there is no variable called db yet"
assert isinstance(kv.db, dict), "db should be a dictionary: db = {}"
assert "name" in kv.db, 'db has no key "name" yet'
assert "city" in kv.db, 'db has no key "city" yet'
assert isinstance(kv.db["name"], str), 'db["name"] should hold text, in quotes'
assert isinstance(kv.db["city"], str), 'db["city"] should hold text, in quotes'
