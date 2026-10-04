import rag

assert hasattr(rag, "chunk"), "no function called chunk yet"
text = "w0 w1 w2 w3 w4 w5 w6 w7 w8 w9"
got = rag.chunk("doc", text, 4, 1)
want = [("doc#0", "w0 w1 w2 w3"), ("doc#1", "w3 w4 w5 w6"), ("doc#2", "w6 w7 w8 w9")]
assert got == want, "chunk(10 words, size=4, overlap=1) should be %r, got %r" % (want, got)
got = rag.chunk("doc", text + " w10", 4, 1)
assert got[-1] == ("doc#3", "w9 w10"), "with 11 words the last chunk is the 2 leftovers ('doc#3', 'w9 w10'), got %r" % (got[-1:],)
got = rag.chunk("d", text, 5, 0)
assert got == [("d#0", "w0 w1 w2 w3 w4"), ("d#1", "w5 w6 w7 w8 w9")], "overlap 0 means chunks side by side, got %r" % (got,)
got = rag.chunk("d", "just three words", 10, 2)
assert got == [("d#0", "just three words")], "a text shorter than size is one chunk, got %r" % (got,)
got = rag.chunk("d", "a  b\n\nc\td", 2, 0)
assert got == [("d#0", "a b"), ("d#1", "c d")], "words are split on any whitespace and joined with ONE space, got %r" % (got,)
assert rag.chunk("d", "", 3, 1) == [], "an empty text has no chunks"
assert rag.chunk("d", "   ", 3, 1) == [], "a text of only spaces has no chunks"
got = rag.chunk("d", "a b c d", 3, 1)
assert got == [("d#0", "a b c"), ("d#1", "c d")], "stop once a chunk reaches the last word: expected 2 chunks, got %r" % (got,)
for size, overlap in ((0, 0), (3, 3), (3, 5), (3, -1)):
    try:
        rag.chunk("d", text, size, overlap)
    except ValueError:
        pass
    else:
        raise AssertionError("chunk(size=%d, overlap=%d) should raise ValueError" % (size, overlap))
