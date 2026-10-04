import time


class KV:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.data = {}
        self.expires = {}
        self.stack = []

    def alive(self, key):
        if key not in self.data:
            return False
        if key in self.expires and self.clock() >= self.expires[key]:
            return False
        return True

    def put(self, key, value, ttl=None):
        self.data[key] = value
        if ttl is None:
            self.expires.pop(key, None)
        else:
            self.expires[key] = self.clock() + ttl

    def get(self, key):
        if not self.alive(key):
            return None
        return self.data[key]

    def delete(self, key):
        if not self.alive(key):
            return False
        del self.data[key]
        self.expires.pop(key, None)
        return True

    def count(self):
        n = 0
        for key in self.data:
            if self.alive(key):
                n = n + 1
        return n

    def find(self, value):
        keys = []
        for key, v in self.data.items():
            if v == value and self.alive(key):
                keys.append(key)
        return sorted(keys)

    def begin(self):
        self.stack.append((dict(self.data), dict(self.expires)))

    def rollback(self):
        if not self.stack:
            raise RuntimeError("no transaction")
        self.data, self.expires = self.stack.pop()

    def commit(self):
        if not self.stack:
            raise RuntimeError("no transaction")
        self.stack.pop()
