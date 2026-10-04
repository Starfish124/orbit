import bank
from _earlier import check_up_to

b = bank.Bank()
for name in ("schedule_payment", "cancel_payment"):
    assert hasattr(b, name), "Bank has no method %s yet" % name
check_up_to(5)

b.create_account(1, "a"); b.deposit(2, "a", 1000); b.create_account(3, "b")
assert b.schedule_payment(4, "zz", 100, 5) is None, "scheduling from an unknown account should return None"
try:
    b.schedule_payment(4, "a", 0, 5)
except ValueError:
    pass
else:
    raise AssertionError("schedule_payment with amount 0 should raise ValueError (stage 3 rule)")

p1 = b.schedule_payment(5, "a", 300, 10)       # due at 15
assert p1 == "payment1", "the first payment's id should be 'payment1', got %r" % (p1,)
p2 = b.schedule_payment(6, "a", 200, 3)        # due at 9
assert p2 == "payment2", "the second payment's id should be 'payment2', got %r" % (p2,)
assert b.get_balance(8, "a") == 1000, "at time 8 nothing is due yet: a should still have 1000, got %r" % (b.get_balance(8, "a"),)
got = b.get_balance(9, "a")
assert got == 800, "payment2 is due at 9 = 6 + 3: it must run BEFORE get_balance(9, ..), expected 800, got %r" % (got,)
assert b.cancel_payment(10, "b", p1) is False, "b can't cancel a's payment: expected False"
assert b.cancel_payment(11, "a", "payment99") is False, "cancelling an id that doesn't exist should be False"

p3 = b.schedule_payment(12, "a", 5000, 1)      # due at 13, a can't afford it
assert p3 == "payment3", "ids keep counting: expected 'payment3', got %r" % (p3,)
got = b.top_spenders(20, 5)
assert got == ["a(500)", "b(0)"], (
    "by time 20, payment3 (too big) was skipped and payment1 (300) ran; payments count as "
    "outgoing, so top_spenders should be ['a(500)', 'b(0)'], got %r" % (got,))
got = b.history(22, "a")
assert got == [(2, 1000), (9, -200), (15, -300)], (
    "a payment is recorded at its DUE time: history should be [(2, 1000), (9, -200), (15, -300)], got %r" % (got,))
assert b.balance_at(23, "a", 14) == 800, "balance_at(.., 'a', 14) is before payment1 ran: expected 800"
assert b.cancel_payment(24, "a", p1) is False, "payment1 already ran: cancelling it should be False"

p4 = b.schedule_payment(25, "a", 100, 10)
assert b.cancel_payment(26, "a", p4) is True, "cancelling a pending payment should be True"
assert b.cancel_payment(27, "a", p4) is False, "cancelling the same payment twice should be False the second time"
assert b.get_balance(40, "a") == 500, "a cancelled payment must never run: expected 500, got %r" % (b.get_balance(40, "a"),)

b.schedule_payment(41, "a", 400, 20)           # due at 61
b.schedule_payment(42, "a", 400, 5)            # due at 47: runs first
got = b.withdraw(70, "a", 200)
assert got is None, (
    "at 70 the payment due at 47 runs first (500 -> 100), the one due at 61 is skipped, THEN the "
    "withdraw of 200 finds only 100: expected None, got %r" % (got,))
assert b.get_balance(71, "a") == 100, "a should have 100 left, got %r" % (b.get_balance(71, "a"),)

b.schedule_payment(80, "a", 70, 10)            # due at 90, scheduled first
b.schedule_payment(81, "a", 60, 9)             # also due at 90
assert b.get_balance(95, "a") == 30, (
    "two payments due at the same time run in the order they were scheduled: 70 runs, "
    "then 60 can't be paid; expected 30, got %r" % (b.get_balance(95, "a"),))
