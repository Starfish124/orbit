class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRU:
    def __init__(self, capacity, on_evict=None):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self.on_evict = on_evict
        self.nodes = {}
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _unhook(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_last(self, node):
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _evict_one(self):
        oldest = self.head.next
        self._unhook(oldest)
        del self.nodes[oldest.key]
        self.evictions += 1
        if self.on_evict is not None:
            self.on_evict(oldest.key, oldest.value)

    def put(self, key, value):
        if key in self.nodes:
            node = self.nodes[key]
            node.value = value
            self._unhook(node)
            self._add_last(node)
            return
        if len(self.nodes) == self.capacity:
            self._evict_one()
        node = Node(key, value)
        self.nodes[key] = node
        self._add_last(node)

    def get(self, key):
        if key not in self.nodes:
            self.misses += 1
            return None
        self.hits += 1
        node = self.nodes[key]
        self._unhook(node)
        self._add_last(node)
        return node.value

    def size(self):
        return len(self.nodes)

    def stats(self):
        return {"hits": self.hits, "misses": self.misses, "evictions": self.evictions}

    def peek(self, key):
        if key not in self.nodes:
            return None
        return self.nodes[key].value

    def resize(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        while len(self.nodes) > self.capacity:
            self._evict_one()
