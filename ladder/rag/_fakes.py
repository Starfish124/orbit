"""Fakes for the rag tests: stand-ins for the parts a real system rents.

embed(text) is a toy embedding model. Each position in the returned list is
one topic; the number there is how many words of that topic the text uses.
Like a real embedder it knows synonyms (puppy, canine and dog all count as
'pet'); unlike BM25 it is blind to words it never learned (codes, names).
"""

TOPICS = [
    ("pet", {"dog", "dogs", "puppy", "canine", "pet", "pets", "cat", "kitten", "vet"}),
    ("vehicle", {"car", "cars", "automobile", "vehicle", "engine", "motor", "tyre"}),
    ("money", {"bank", "money", "loan", "cash", "mortgage", "finance", "income"}),
    ("food", {"bread", "bake", "oven", "flour", "recipe", "yeast", "cake"}),
    ("weather", {"rain", "storm", "weather", "forecast", "sunny", "wind"}),
]


def _words(text):
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return cleaned.split()


def embed(text):
    words = _words(text)
    return [float(sum(1 for w in words if w in vocab)) for _, vocab in TOPICS]
