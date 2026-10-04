import bank
from _earlier import check_up_to

b = bank.Bank()
for name in ("history", "balance_at"):
    assert hasattr(b, name), "Bank has no method %s yet" % name
check_up_to(4)

b.create_account(1, "a"); b.create_account(2, "b")
assert b.history(3, "a") == [], "a new account has an empty history, got %r" % (b.history(3, "a"),)
b.deposit(10, "a", 500)
b.withdraw(20, "a", 9999)              # fails: not recorded
b.transfer(30, "a", "b", 200)
b.withdraw(40, "b", 50)
b.deposit(50, "a", 1)

got = b.history(60, "a")
assert got == [(10, 500), (30, -200), (50, 1)], (
    "history of a should be [(10, 500), (30, -200), (50, 1)]: (timestamp, change), "
    "oldest first, failed operations left out; got %r" % (got,))
got = b.history(61, "b")
assert got == [(30, 200), (40, -50)], "a transfer shows up on BOTH sides: b should be [(30, 200), (40, -50)], got %r" % (got,)
assert b.history(62, "zz") is None, "history of an unknown account should be None"

got.append("junk")
assert b.history(63, "b") == [(30, 200), (40, -50)], (
    "history must hand back a copy: changing the returned list changed the bank")

checks = [(5, 0), (10, 500), (29, 500), (30, 300), (49, 300), (50, 301), (1000, 301)]
for time, want in checks:
    got = b.balance_at(70, "a", time)
    assert got == want, "balance_at(.., 'a', %d) should be %d, got %r (a change AT that time counts)" % (time, want, got)
assert b.balance_at(71, "b", 35) == 200, "balance_at(.., 'b', 35) should be 200, got %r" % (b.balance_at(71, "b", 35),)
assert b.balance_at(72, "zz", 10) is None, "balance_at of an unknown account should be None"
assert b.get_balance(73, "a") == 301, "get_balance still works"
