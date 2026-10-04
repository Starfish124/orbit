class KV:
    def __init__(self):
        self.data = {}
        self.stack = []

    def put(self, key, value):
        self.data[key] = value

    def get(self, key):
        if key not in self.data:
            return None
        return self.data[key]

    def delete(self, key):
        if key not in self.data:
            return False
        del self.data[key]
        return True

    def count(self):
        n = 0
        for key in self.data:
            n = n + 1
        return n

    def find(self, value):
        keys = []
        for key, v in self.data.items():
            if v == value:
                keys.append(key)
        return sorted(keys)

    def begin(self):
        self.stack.append(dict(self.data))

    def rollback(self):
        if not self.stack:
            raise RuntimeError("no transaction")
        self.data = self.stack.pop()

    def commit(self):
        if not self.stack:
            raise RuntimeError("no transaction")
        self.stack.pop()
