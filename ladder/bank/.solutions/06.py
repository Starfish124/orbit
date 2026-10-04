class Bank:
    def __init__(self):
        self.balances = {}
        self.outgoing = {}
        self.records = {}
        self.pending = []
        self.payment_count = 0

    def _check_amount(self, amount):
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError("amount must be a positive whole number of cents")

    def _change(self, ts, account_id, delta):
        self.balances[account_id] += delta
        self.records[account_id].append((ts, delta))
        if delta < 0:
            self.outgoing[account_id] += -delta

    def _process(self, ts):
        # run every payment that is due by now, earliest first, before anything else
        due = [p for p in self.pending if p["due"] <= ts]
        due.sort(key=lambda p: (p["due"], p["number"]))
        for p in due:
            self.pending.remove(p)
            if self.balances[p["account"]] >= p["amount"]:
                self._change(p["due"], p["account"], -p["amount"])

    def create_account(self, ts, account_id):
        self._process(ts)
        if account_id in self.balances:
            return False
        self.balances[account_id] = 0
        self.outgoing[account_id] = 0
        self.records[account_id] = []
        return True

    def deposit(self, ts, account_id, amount):
        self._process(ts)
        self._check_amount(amount)
        if account_id not in self.balances:
            return None
        self._change(ts, account_id, amount)
        return self.balances[account_id]

    def get_balance(self, ts, account_id):
        self._process(ts)
        if account_id not in self.balances:
            return None
        return self.balances[account_id]

    def withdraw(self, ts, account_id, amount):
        self._process(ts)
        self._check_amount(amount)
        if account_id not in self.balances:
            return None
        if self.balances[account_id] < amount:
            return None
        self._change(ts, account_id, -amount)
        return self.balances[account_id]

    def transfer(self, ts, source, target, amount):
        self._process(ts)
        self._check_amount(amount)
        if source == target:
            return None
        if source not in self.balances or target not in self.balances:
            return None
        if self.balances[source] < amount:
            return None
        self._change(ts, source, -amount)
        self._change(ts, target, amount)
        return self.balances[source]

    def top_spenders(self, ts, n):
        self._process(ts)
        pairs = sorted(self.outgoing.items(), key=lambda item: (-item[1], item[0]))
        return [f"{account_id}({total})" for account_id, total in pairs[:n]]

    def history(self, ts, account_id):
        self._process(ts)
        if account_id not in self.records:
            return None
        return list(self.records[account_id])

    def balance_at(self, ts, account_id, time):
        self._process(ts)
        if account_id not in self.records:
            return None
        total = 0
        for when, delta in self.records[account_id]:
            if when <= time:
                total += delta
        return total

    def schedule_payment(self, ts, account_id, amount, delay):
        self._process(ts)
        self._check_amount(amount)
        if account_id not in self.balances:
            return None
        self.payment_count += 1
        self.pending.append({"number": self.payment_count, "id": f"payment{self.payment_count}",
                             "account": account_id, "amount": amount, "due": ts + delay})
        return f"payment{self.payment_count}"

    def cancel_payment(self, ts, account_id, payment_id):
        self._process(ts)
        for p in self.pending:
            if p["id"] == payment_id and p["account"] == account_id:
                self.pending.remove(p)
                return True
        return False
