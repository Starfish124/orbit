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
