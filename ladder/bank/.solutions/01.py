class Bank:
    def __init__(self):
        self.balances = {}

    def create_account(self, ts, account_id):
        if account_id in self.balances:
            return False
        self.balances[account_id] = 0
        return True

    def deposit(self, ts, account_id, amount):
        if account_id not in self.balances:
            return None
        self.balances[account_id] += amount
        return self.balances[account_id]

    def get_balance(self, ts, account_id):
        if account_id not in self.balances:
            return None
        return self.balances[account_id]
