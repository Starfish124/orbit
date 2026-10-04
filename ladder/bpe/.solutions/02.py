def to_bytes(text):
    return list(text.encode("utf-8"))


def from_bytes(ids):
    return bytes(ids).decode("utf-8")


def get_stats(ids):
    counts = {}
    for i in range(len(ids) - 1):
        pair = (ids[i], ids[i + 1])
        counts[pair] = counts.get(pair, 0) + 1
    return counts
