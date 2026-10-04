class LRU:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self.data = {}
        self.order = []

    def put(self, key, value):
        if key not in self.data and len(self.data) == self.capacity:
            oldest = self.order.pop(0)
            del self.data[oldest]
        self.data[key] = value
        self.order.append(key)

    def get(self, key):
        if key not in self.data:
            return None
        return self.data[key]

    def size(self):
        return len(self.data)
