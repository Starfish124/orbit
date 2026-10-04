import time

import lru


def per_op(cap, ops=10000):
    """Seconds per get+put on a FULL cache of `cap` keys, best of 3."""
    c = lru.LRU(cap)
    for i in range(cap):
        c.put(i, i)
    best = None
    for _ in range(3):
        t = time.perf_counter()
        for i in range(ops):
            k = (i * 7919) % cap
            c.get(k)
            c.put(k, i)
        dt = (time.perf_counter() - t) / ops
        best = dt if best is None else min(best, dt)
    return best


def check_speed():
    small, big = per_op(50), per_op(5000)
    ratio = big / small
    assert ratio < 4, (
        "a 5000-key cache is %.0fx slower per operation than a 50-key one: something "
        "walks through all the keys (list.remove, list.pop(0), `in` on a list). "
        "Every get and put must take the same time however full the cache is." % ratio)
