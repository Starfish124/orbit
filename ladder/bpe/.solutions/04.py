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


def merge(ids, pair, new_id):
    out = []
    i = 0
    while i < len(ids):
        if i + 1 < len(ids) and (ids[i], ids[i + 1]) == pair:
            out.append(new_id)
            i = i + 2
        else:
            out.append(ids[i])
            i = i + 1
    return out


def most_common(stats):
    best = None
    for pair in stats:
        if best is None or stats[pair] > stats[best]:
            best = pair
    return best


def train(text, vocab_size):
    if vocab_size < 256:
        raise ValueError("vocab_size must be at least 256")
    ids = to_bytes(text)
    merges = {}
    for new_id in range(256, vocab_size):
        stats = get_stats(ids)
        if not stats:
            break
        pair = most_common(stats)
        ids = merge(ids, pair, new_id)
        merges[pair] = new_id
    return merges
