class KV:
    def __init__(self):
        self.data = {}
        self.saved = None

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
        self.saved = dict(self.data)

    def rollback(self):
        if self.saved is None:
            raise RuntimeError("no transaction")
        self.data = self.saved
        self.saved = None

    def commit(self):
        if self.saved is None:
            raise RuntimeError("no transaction")
        self.saved = None
