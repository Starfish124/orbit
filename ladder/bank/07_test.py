import bank
from _earlier import check_up_to

b = bank.Bank()
assert hasattr(b, "merge_accounts"), "Bank has no method merge_accounts yet"
check_up_to(6)

for i, name in enumerate(["a", "b", "c"]):
    b.create_account(i + 1, name)
b.deposit(4, "a", 100); b.deposit(5, "b", 300)
b.withdraw(6, "b", 50)
b.transfer(7, "a", "b", 20)                    # a 80, b 270
p = b.schedule_payment(8, "b", 100, 10)         # due at 18, belongs to b

assert b.merge_accounts(9, "a", "a") is False, "merging an account with itself should be False"
assert b.merge_accounts(10, "a", "zz") is False, "merging in an unknown account should be False"
assert b.merge_accounts(11, "zz", "a") is False, "merging into an unknown account should be False"
assert b.merge_accounts(12, "a", "b") is True, "merge_accounts(.., 'a', 'b') should be True"

assert b.get_balance(13, "a") == 350, "a should hold 80 + 270 = 350, got %r" % (b.get_balance(13, "a"),)
assert b.get_balance(13, "b") is None, "b is deleted after the merge: get_balance should be None"
assert b.deposit(14, "b", 5) is None, "b is deleted: deposit should return None"
assert b.history(15, "b") is None and b.balance_at(16, "b", 10) is None, "b is deleted: history and balance_at are None"
got = b.history(17, "a")
assert got == [(4, 100), (5, 300), (6, -50), (7, -20), (7, 20)], (
    "a's history should now hold both histories, sorted by time: "
    "[(4, 100), (5, 300), (6, -50), (7, -20), (7, 20)], got %r" % (got,))
assert b.balance_at(18, "a", 6) == 350, "balance_at(.., 'a', 6) should count b's old records too: 350"
assert b.get_balance(19, "a") == 250, (
    "b's pending payment (100, due 18) moves to a and runs from a: expected 250, got %r" % (b.get_balance(19, "a"),))
got = b.top_spenders(20, 5)
assert got == ["a(170)", "c(0)"], (
    "a's outgoing = its own 20 + b's 50 + the payment 100 = 170; b is gone: expected ['a(170)', 'c(0)'], got %r" % (got,))

b.deposit(21, "c", 500); b.create_account(22, "d")
q = b.schedule_payment(23, "c", 100, 50)
assert b.merge_accounts(24, "d", "c") is True, "merging c into d should be True"
assert b.cancel_payment(25, "c", q) is False, "c is gone, so c can't cancel its old payment: False"
assert b.cancel_payment(26, "d", q) is True, "the payment moved to d: d can cancel it, True"

assert b.create_account(27, "b") is True, "the id 'b' is free again after the merge: create_account should be True"
assert b.get_balance(28, "b") == 0 and b.history(29, "b") == [], "a re-created b starts fresh: balance 0, empty history"
