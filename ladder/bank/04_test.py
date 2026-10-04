import bank
from _earlier import check_up_to

b = bank.Bank()
assert hasattr(b, "top_spenders"), "Bank has no method top_spenders yet"
check_up_to(3)

for i, name in enumerate(["dave", "bob", "alice", "carol"]):
    b.create_account(i, name)
    b.deposit(10 + i, name, 1000)
b.withdraw(20, "bob", 300)
b.transfer(21, "alice", "dave", 200)
b.withdraw(22, "alice", 100)
b.withdraw(23, "carol", 5000)          # fails: must not count
b.deposit(24, "carol", 999)            # money IN: must not count

got = b.top_spenders(25, 2)
assert got == ["alice(300)", "bob(300)"], (
    "top_spenders(.., 2) should be ['alice(300)', 'bob(300)']: most outgoing first, "
    "a tie broken by id A-Z; got %r" % (got,))
got = b.top_spenders(26, 10)
assert got == ["alice(300)", "bob(300)", "carol(0)", "dave(0)"], (
    "asking for more than exist returns them all, zero spenders included, got %r" % (got,))
assert b.top_spenders(27, 0) == [], "top_spenders(.., 0) should be an empty list"
b.transfer(28, "dave", "carol", 1200)
assert b.top_spenders(29, 1) == ["dave(1200)"], (
    "dave just sent 1200 and should lead, got %r" % (b.top_spenders(29, 1),))
assert bank.Bank().top_spenders(1, 3) == [], "an empty bank has no spenders: []"
