class Bank:
    def __init__(self):
        self.balances = {}
        self.outgoing = {}

    def _check_amount(self, amount):
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError("amount must be a positive whole number of cents")

    def create_account(self, ts, account_id):
        if account_id in self.balances:
            return False
        self.balances[account_id] = 0
        self.outgoing[account_id] = 0
        return True

    def deposit(self, ts, account_id, amount):
        self._check_amount(amount)
        if account_id not in self.balances:
            return None
        self.balances[account_id] += amount
        return self.balances[account_id]

    def get_balance(self, ts, account_id):
        if account_id not in self.balances:
            return None
        return self.balances[account_id]

    def withdraw(self, ts, account_id, amount):
        self._check_amount(amount)
        if account_id not in self.balances:
            return None
        if self.balances[account_id] < amount:
            return None
        self.balances[account_id] -= amount
        self.outgoing[account_id] += amount
        return self.balances[account_id]

    def transfer(self, ts, source, target, amount):
        self._check_amount(amount)
        if source == target:
            return None
        if source not in self.balances or target not in self.balances:
            return None
        if self.balances[source] < amount:
            return None
        self.balances[source] -= amount
        self.balances[target] += amount
        self.outgoing[source] += amount
        return self.balances[source]

    def top_spenders(self, ts, n):
        pairs = sorted(self.outgoing.items(), key=lambda item: (-item[1], item[0]))
        return [f"{account_id}({total})" for account_id, total in pairs[:n]]
