"""Short re-checks of earlier stages, so a new feature can't quietly break an old one."""
import bank


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def stage1():
    b = bank.Bank()
    assert b.create_account(1, "a") is True and b.create_account(2, "a") is False, \
        "(stage 1 broke) create_account: True the first time, False for an existing id"
    assert b.deposit(3, "a", 500) == 500 and b.deposit(4, "zz", 5) is None, \
        "(stage 1 broke) deposit returns the new balance, or None for an unknown account"
    assert b.get_balance(5, "a") == 500 and b.get_balance(6, "zz") is None, \
        "(stage 1 broke) get_balance returns the balance, or None for an unknown account"
    assert bank.Bank().get_balance(7, "a") is None, "(stage 1 broke) two Banks must not share accounts"


def stage2():
    b = bank.Bank()
    b.create_account(1, "a"); b.create_account(2, "b"); b.deposit(3, "a", 100)
    assert b.withdraw(4, "a", 101) is None and b.withdraw(5, "a", 40) == 60, \
        "(stage 2 broke) withdraw: None when short of money, else the new balance"
    assert b.transfer(6, "a", "a", 1) is None and b.transfer(7, "a", "zz", 1) is None, \
        "(stage 2 broke) transfer to yourself or to an unknown account returns None"
    assert b.transfer(8, "a", "b", 60) == 0 and b.get_balance(9, "b") == 60, \
        "(stage 2 broke) transfer returns the source's new balance and credits the target"


def stage3():
    b = bank.Bank()
    b.create_account(1, "a")
    for bad in (0, -5, 1.5):
        assert _raises(lambda: b.deposit(2, "a", bad)), \
            "(stage 3 broke) deposit of %r should raise ValueError" % (bad,)
    assert _raises(lambda: b.withdraw(3, "zz", -1)), "(stage 3 broke) withdraw of -1 should raise ValueError"
    assert _raises(lambda: b.transfer(4, "a", "a", 0)), "(stage 3 broke) transfer of 0 should raise ValueError"


def stage4():
    b = bank.Bank()
    for i, name in enumerate(["c", "a", "b"]):
        b.create_account(i, name)
        b.deposit(10 + i, name, 100)
    b.withdraw(20, "b", 30); b.transfer(21, "a", "c", 30); b.withdraw(22, "c", 50)
    got = b.top_spenders(23, 5)
    assert got == ["c(50)", "a(30)", "b(30)"], \
        "(stage 4 broke) top_spenders should be ['c(50)', 'a(30)', 'b(30)'], got %r" % (got,)


def stage5():
    b = bank.Bank()
    b.create_account(1, "a"); b.create_account(2, "b")
    b.deposit(3, "a", 100); b.withdraw(4, "a", 500); b.transfer(5, "a", "b", 40)
    assert b.history(6, "a") == [(3, 100), (5, -40)], \
        "(stage 5 broke) history of a should be [(3, 100), (5, -40)], got %r" % (b.history(6, "a"),)
    assert b.balance_at(7, "a", 4) == 100 and b.balance_at(8, "zz", 4) is None, \
        "(stage 5 broke) balance_at(.., 'a', 4) should be 100, unknown account None"


def stage6():
    b = bank.Bank()
    b.create_account(1, "a"); b.deposit(2, "a", 100)
    p = b.schedule_payment(3, "a", 30, 5)
    q = b.schedule_payment(4, "a", 10, 5)
    assert b.cancel_payment(5, "zz", q) is False, "(stage 6 broke) only the owner may cancel a payment"
    assert b.cancel_payment(5, "a", q) is True, "(stage 6 broke) cancel_payment of a pending payment is True"
    assert b.get_balance(8, "a") == 70 and b.cancel_payment(9, "a", p) is False, \
        "(stage 6 broke) a due payment runs before the next operation and can't be cancelled after"


def stage7():
    b = bank.Bank()
    b.create_account(1, "a"); b.create_account(2, "b"); b.deposit(3, "b", 50)
    assert b.merge_accounts(4, "a", "b") is True and b.get_balance(5, "a") == 50 \
        and b.get_balance(6, "b") is None, "(stage 7 broke) merge moves b's money into a and deletes b"


def check_up_to(n):
    for check in [stage1, stage2, stage3, stage4, stage5, stage6, stage7][:n]:
        check()
