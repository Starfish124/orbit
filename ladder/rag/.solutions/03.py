import math


def chunk(doc_id, text, size, overlap):
    if size < 1:
        raise ValueError("size must be at least 1")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be between 0 and size - 1")
    words = text.split()
    step = size - overlap
    chunks = []
    start = 0
    while start < len(words):
        piece = words[start:start + size]
        chunks.append((doc_id + "#" + str(len(chunks)), " ".join(piece)))
        if start + size >= len(words):
            break
        start = start + step
    return chunks


def tokenize(text):
    cleaned = ""
    for ch in text.lower():
        if ch.isalnum():
            cleaned = cleaned + ch
        else:
            cleaned = cleaned + " "
    return cleaned.split()


def term_counts(tokens):
    counts = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    return counts


def idf_table(docs):
    n = len(docs)
    df = {}
    for tokens in docs:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    idf = {}
    for t in df:
        idf[t] = math.log((n + 1) / (df[t] + 1)) + 1
    return idf


def tfidf(tokens, idf):
    vec = {}
    counts = term_counts(tokens)
    for t in counts:
        if t in idf:
            vec[t] = counts[t] * idf[t]
    return vec


def cosine(a, b):
    dot = 0.0
    for t in a:
        if t in b:
            dot = dot + a[t] * b[t]
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def top_k(scores, k):
    hits = [(i, s) for i, s in scores.items() if s > 0]
    hits = sorted(hits, key=lambda pair: (-pair[1], pair[0]))
    return hits[:k]
