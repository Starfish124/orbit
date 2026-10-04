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


def bm25(query_tokens, docs, k1=1.5, b=0.75):
    scores = {}
    for i in docs:
        scores[i] = 0.0
    n = len(docs)
    if n == 0:
        return scores
    avgdl = sum(len(tokens) for tokens in docs.values()) / n
    if avgdl == 0:
        return scores
    df = {}
    for tokens in docs.values():
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    counts = {}
    for i in docs:
        counts[i] = term_counts(docs[i])
    for t in set(query_tokens):
        if t not in df:
            continue
        idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
        for i in docs:
            f = counts[i].get(t, 0)
            if f == 0:
                continue
            norm = 1 - b + b * len(docs[i]) / avgdl
            scores[i] = scores[i] + idf * f * (k1 + 1) / (f + k1 * norm)
    return scores


def build_prompt(question, passages, budget):
    header = "Answer the question using only the sources below. Cite them like [1].\n\n"
    footer = "Question: " + question + "\nAnswer:"
    used = list(passages)
    while True:
        blocks = ""
        for n, (chunk_id, text) in enumerate(used, 1):
            blocks = blocks + "[" + str(n) + "] " + chunk_id + "\n" + text + "\n\n"
        prompt = header + blocks + footer
        if len(prompt) <= budget:
            return prompt, [chunk_id for chunk_id, _ in used]
        if not used:
            raise ValueError("budget too small for the question alone")
        used.pop()


def recall_at_k(ranked, relevant, k):
    found = 0
    for i in relevant:
        if i in ranked[:k]:
            found = found + 1
    return found / len(relevant)


def reciprocal_rank(ranked, relevant):
    for pos, i in enumerate(ranked, 1):
        if i in relevant:
            return 1 / pos
    return 0.0


def evaluate(search, labeled, k):
    if not labeled:
        raise ValueError("need at least one labeled question")
    recall = 0.0
    rr = 0.0
    for question, relevant in labeled:
        ranked = [i for i, _ in search(question, k)]
        recall = recall + recall_at_k(ranked, relevant, k)
        rr = rr + reciprocal_rank(ranked, relevant)
    return {"recall": recall / len(labeled), "mrr": rr / len(labeled)}


class Index:
    def __init__(self, size=100, overlap=20):
        self.size = size
        self.overlap = overlap
        self.texts = {}
        self.tokens = {}
        self.doc_ids = set()

    def add_documents(self, docs):
        for doc_id in docs:
            if doc_id in self.doc_ids:
                raise ValueError("document already indexed: " + doc_id)
        for doc_id, text in docs.items():
            self.doc_ids.add(doc_id)
            for chunk_id, piece in chunk(doc_id, text, self.size, self.overlap):
                self.texts[chunk_id] = piece
                self.tokens[chunk_id] = tokenize(piece)

    def text(self, chunk_id):
        return self.texts[chunk_id]

    def search(self, query, k=3):
        return top_k(bm25(tokenize(query), self.tokens), k)

    def answer(self, question, llm, k=3, min_score=1.0, budget=1500):
        hits = self.search(question, k)
        if not hits or hits[0][1] < min_score:
            return {"answer": "I don't know", "sources": []}
        passages = [(chunk_id, self.text(chunk_id)) for chunk_id, _ in hits]
        prompt, used = build_prompt(question, passages, budget)
        return {"answer": llm(prompt), "sources": used}
