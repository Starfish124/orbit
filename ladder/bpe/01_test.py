import bpe

assert hasattr(bpe, "to_bytes"), "no function called to_bytes yet"
assert hasattr(bpe, "from_bytes"), "no function called from_bytes yet"
got = bpe.to_bytes("hi")
assert got == [104, 105], "to_bytes('hi') should be [104, 105], got %r" % (got,)
assert type(got) is list, "to_bytes should return a list of ints, got a %s" % type(got).__name__
got = bpe.to_bytes("é")
assert got == [195, 169], "'é' is TWO bytes in UTF-8: expected [195, 169], got %r" % (got,)
assert bpe.to_bytes("") == [], "to_bytes('') should be []"
got = bpe.from_bytes([104, 105])
assert got == "hi", "from_bytes([104, 105]) should be 'hi', got %r" % (got,)
for text in ["hello", "café", "héllo wörld", "日本", "👋", ""]:
    back = bpe.from_bytes(bpe.to_bytes(text))
    assert back == text, "round trip broke: %r -> bytes -> %r" % (text, back)
assert len(bpe.to_bytes("👋")) == 4, "an emoji is 4 bytes in UTF-8, got %d" % len(bpe.to_bytes("👋"))
