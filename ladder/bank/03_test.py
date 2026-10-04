import bank
from _earlier import check_up_to

check_up_to(2)

b = bank.Bank()
b.create_account(1, "a"); b.create_account(2, "b")
b.deposit(3, "a", 1000)


def raises(what, fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("%s should raise ValueError" % what)


for bad in (0, -5, 10.5, "10"):
    raises("deposit of %r" % (bad,), lambda: b.deposit(4, "a", bad))
    raises("withdraw of %r" % (bad,), lambda: b.withdraw(5, "a", bad))
    raises("transfer of %r" % (bad,), lambda: b.transfer(6, "a", "b", bad))
assert b.get_balance(7, "a") == 1000, "rejected amounts must not change the balance, a has %r" % (b.get_balance(7, "a"),)
assert b.get_balance(8, "b") == 0, "rejected transfers must not change b, b has %r" % (b.get_balance(8, "b"),)

raises("deposit of -5 to an unknown account (check the amount first)", lambda: b.deposit(9, "zz", -5))
raises("transfer of 0 to yourself (check the amount first)", lambda: b.transfer(10, "a", "a", 0))

assert b.deposit(11, "a", 10) == 1010, "a positive whole number of cents still works"
assert b.withdraw(12, "a", 1010) == 0, "withdrawing the exact balance still works and gives 0"
