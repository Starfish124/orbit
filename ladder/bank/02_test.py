import bank
from _earlier import check_up_to

b = bank.Bank()
for name in ("withdraw", "transfer"):
    assert hasattr(b, name), "Bank has no method %s yet" % name
check_up_to(1)

b.create_account(1, "a"); b.create_account(2, "b")
b.deposit(3, "a", 100)
assert b.withdraw(4, "zz", 10) is None, "withdraw from an unknown account should return None"
assert b.withdraw(5, "a", 101) is None, "withdrawing 101 from 100 should return None (not enough money)"
assert b.get_balance(6, "a") == 100, "a failed withdraw must not change the balance, got %r" % (b.get_balance(6, "a"),)
got = b.withdraw(7, "a", 30)
assert got == 70, "withdraw 30 from 100 should return 70, got %r" % (got,)

assert b.transfer(8, "a", "a", 10) is None, "transfer to the same account should return None"
assert b.transfer(9, "zz", "a", 10) is None, "transfer from an unknown account should return None"
assert b.transfer(10, "a", "zz", 10) is None, "transfer to an unknown account should return None"
assert b.get_balance(11, "a") == 70, "failed transfers must not touch the money, a has %r" % (b.get_balance(11, "a"),)
assert b.transfer(12, "a", "b", 71) is None, "transferring 71 when a has 70 should return None"
assert b.get_balance(13, "b") == 0, "a failed transfer must not give b anything, b has %r" % (b.get_balance(13, "b"),)
got = b.transfer(14, "a", "b", 70)
assert got == 0, "transfer of everything (70) is allowed and returns a's new balance 0, got %r" % (got,)
assert b.get_balance(15, "b") == 70, "b should now have 70, got %r" % (b.get_balance(15, "b"),)
assert b.withdraw(16, "a", 1) is None, "a is at 0: any withdraw should return None"
