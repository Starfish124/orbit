import bank

assert hasattr(bank, "Bank"), "there is no class called Bank yet"
b = bank.Bank()
for name in ("create_account", "deposit", "get_balance"):
    assert hasattr(b, name), "Bank has no method %s yet" % name

got = b.create_account(1, "alice")
assert got is True, "create_account should return True for a new id, got %r" % (got,)
assert b.create_account(2, "alice") is False, "creating 'alice' a second time should return False"
assert b.create_account(3, "bob") is True, "a different id ('bob') should work: expected True"
assert b.get_balance(4, "alice") == 0, "a new account starts at 0, got %r" % (b.get_balance(4, "alice"),)

got = b.deposit(5, "alice", 500)
assert got == 500, "deposit(5, 'alice', 500) should return the new balance 500, got %r" % (got,)
got = b.deposit(6, "alice", 250)
assert got == 750, "a second deposit of 250 should return 750, got %r" % (got,)
got = b.deposit(7, "carol", 100)
assert got is None, "deposit to an account that doesn't exist should return None, got %r" % (got,)
assert b.get_balance(8, "carol") is None, "get_balance of an unknown account should be None"
assert b.get_balance(9, "bob") == 0, "bob never got money: balance should still be 0"
assert b.create_account(10, "alice") is False, "re-creating alice must not reset her money"
assert b.get_balance(11, "alice") == 750, "alice should still have 750, got %r" % (b.get_balance(11, "alice"),)

other = bank.Bank()
assert other.get_balance(1, "alice") is None, "a second Bank() must start empty: accounts belong in __init__"
