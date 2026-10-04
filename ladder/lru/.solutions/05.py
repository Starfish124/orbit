from collections import OrderedDict


class LRU:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self.data = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def put(self, key, value):
        if key in self.data:
            self.data.move_to_end(key)
        elif len(self.data) == self.capacity:
            self.data.popitem(last=False)
            self.evictions += 1
        self.data[key] = value

    def get(self, key):
        if key not in self.data:
            self.misses += 1
            return None
        self.hits += 1
        self.data.move_to_end(key)
        return self.data[key]

    def size(self):
        return len(self.data)

    def stats(self):
        return {"hits": self.hits, "misses": self.misses, "evictions": self.evictions}
