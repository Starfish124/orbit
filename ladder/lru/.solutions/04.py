class LRU:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self.data = {}
        self.order = []
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def put(self, key, value):
        if key in self.data:
            self.order.remove(key)
        elif len(self.data) == self.capacity:
            oldest = self.order.pop(0)
            del self.data[oldest]
            self.evictions += 1
        self.data[key] = value
        self.order.append(key)

    def get(self, key):
        if key not in self.data:
            self.misses += 1
            return None
        self.hits += 1
        self.order.remove(key)
        self.order.append(key)
        return self.data[key]

    def size(self):
        return len(self.data)

    def stats(self):
        return {"hits": self.hits, "misses": self.misses, "evictions": self.evictions}
