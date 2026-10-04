import inspect
import random

import bank
from _earlier import check_up_to

assert "overdraft" in inspect.signature(bank.Bank).parameters, "Bank(overdraft=0) is missing: __init__ takes no overdraft yet"
check_up_to(7)                                  # Bank() with no overdraft behaves exactly as before

try:
    bank.Bank(overdraft=-1)
except ValueError:
    pass
else:
    raise AssertionError("Bank(overdraft=-1) should raise ValueError")

b = bank.Bank(overdraft=100)
b.create_account(1, "a"); b.create_account(2, "b"); b.deposit(3, "a", 50)
assert b.withdraw(4, "a", 150) == -100, "with overdraft 100, a (50) may withdraw 150 and reach -100"
assert b.withdraw(5, "a", 1) is None, "a is at -100, the limit: withdrawing 1 more should be None"
assert b.transfer(6, "a", "b", 1) is None, "the same limit holds for transfer: expected None"
b.schedule_payment(7, "a", 1, 1)
assert b.get_balance(9, "a") == -100, "a payment that would pass the limit is skipped: a stays at -100"
assert b.deposit(10, "a", 100) == 0, "deposit still adds normally: -100 + 100 = 0"
b.schedule_payment(11, "a", 60, 1)
assert b.get_balance(12, "a") == -60, "a scheduled payment may use the overdraft too: 0 - 60 = -60, got %r" % (b.get_balance(12, "a"),)
b.deposit(13, "a", 60)
assert b.transfer(14, "a", "b", 100) == -100, "transfer down to exactly -100 is allowed"
b.create_account(15, "c"); b.create_account(16, "d")
b.withdraw(17, "c", 100); b.withdraw(18, "d", 50)
assert b.merge_accounts(19, "c", "d") is False, "merging c (-100) and d (-50) would give -150, past the limit: False"
b.deposit(20, "d", 60)
assert b.merge_accounts(21, "c", "d") is True and b.get_balance(22, "c") == -90, "c (-100) + d (10) = -90 is fine: merge True"

# a long seeded random run, checked only against rules that must ALWAYS hold
LIMIT = 500
rng = random.Random(2026)
b = bank.Bank(overdraft=LIMIT)
names = ["a", "b", "c", "d", "e", "f"]
money_in = 0          # total successful deposits
moved = 0             # total successful transfers
scheduled = []        # (payment id, account) pairs, to cancel some later
ts = 0
for step in range(1500):
    ts += 1
    op = rng.choice(["create", "create", "deposit", "deposit", "withdraw", "transfer",
                     "transfer", "schedule", "cancel", "merge", "bad"])
    x, y = rng.choice(names), rng.choice(names)
    amount = rng.randint(1, 400)
    if op == "create":
        b.create_account(ts, x)
    elif op == "deposit":
        if b.deposit(ts, x, amount) is not None:
            money_in += amount
    elif op == "withdraw":
        b.withdraw(ts, x, amount)
    elif op == "transfer":
        if b.transfer(ts, x, y, amount) is not None:
            moved += amount
    elif op == "schedule":
        pid = b.schedule_payment(ts, x, amount, rng.randint(0, 20))
        if pid is not None:
            scheduled.append((pid, x))
    elif op == "cancel" and scheduled:
        pid, owner = rng.choice(scheduled)
        b.cancel_payment(ts, rng.choice([owner, x]), pid)
    elif op == "cancel":
        pass
    elif op == "merge":
        b.merge_accounts(ts, x, y)
    else:
        try:
            b.withdraw(ts, x, rng.choice([0, -amount, 0.5]))
        except ValueError:
            pass
        else:
            raise AssertionError("step %d: a zero, negative or fractional amount should raise ValueError" % step)

    ts += 1
    spenders = b.top_spenders(ts, 100)
    outs = [(s[:s.index("(")], int(s[s.index("(") + 1:-1])) for s in spenders]
    assert outs == sorted(outs, key=lambda p: (-p[1], p[0])), "step %d: top_spenders out of order: %r" % (step, spenders)
    total = 0
    for name, out in outs:
        bal = b.get_balance(ts, name)
        hist = b.history(ts, name)
        assert bal >= -LIMIT, "step %d: %s is at %d, below the overdraft limit -%d" % (step, name, bal, LIMIT)
        assert sum(d for _, d in hist) == bal, (
            "step %d: %s's history adds up to %d but its balance is %d: some change skipped the records"
            % (step, name, sum(d for _, d in hist), bal))
        assert [t for t, _ in hist] == sorted(t for t, _ in hist), "step %d: %s's history is not in time order" % (step, name)
        assert b.balance_at(ts, name, ts) == bal, "step %d: balance_at(now) should equal the balance for %s" % (step, name)
        total += bal + out
    assert total == money_in + moved, (
        "step %d: money leaked. Every cent in the bank plus every cent that ever left an account must equal "
        "deposits + transfers (%d), got %d" % (step, money_in + moved, total))
