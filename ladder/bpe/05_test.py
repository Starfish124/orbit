import bpe

assert hasattr(bpe, "Tokenizer"), "no class called Tokenizer yet"
assert bpe.train("aaabdaaabac", 259) == {(97, 97): 256, (256, 97): 257, (257, 98): 258}, "train from stage 4 broke"
fresh = bpe.Tokenizer()
assert fresh.merges == {}, "a new Tokenizer should have no merges, got %r" % (fresh.merges,)
assert len(fresh.vocab) == 256 and fresh.vocab[97] == b"a", "a new Tokenizer's vocab should map each id 0..255 to its single byte, e.g. vocab[97] == b'a'"
assert fresh.encode("hi") == [104, 105], "with no merges, encode is just the bytes: expected [104, 105], got %r" % (fresh.encode("hi"),)
t = bpe.Tokenizer()
t.train("aaabdaaabac", 259)
assert t.merges == {(97, 97): 256, (256, 97): 257, (257, 98): 258}, "t.merges after training is wrong: %r" % (t.merges,)
assert t.vocab[256] == b"aa" and t.vocab[257] == b"aaa" and t.vocab[258] == b"aaab", (
    "vocab[new_id] should be the bytes of both halves glued: 256 b'aa', 257 b'aaa', 258 b'aaab'. Got %r %r %r"
    % (t.vocab.get(256), t.vocab.get(257), t.vocab.get(258)))
got = t.encode("aaabdaaabac")
assert got == [258, 100, 258, 97, 99], "encode('aaabdaaabac') should be [258, 100, 258, 97, 99], got %r" % (got,)
got = t.encode("aaaaa")
assert got == [256, 257], "encode('aaaaa') applies merges in learned order: aa, aa, a -> [256, 257], got %r" % (got,)
assert t.encode("") == [], "encode('') should be []"
assert t.decode([258, 100]) == "aaabd", "decode([258, 100]) should be 'aaabd', got %r" % (t.decode([258, 100]),)
for text in ["aaab", "héllo wörld", "日本語", "👋🏽 hi", "aaa👋aaa", ""]:
    back = t.decode(t.encode(text))
    assert back == text, "round trip broke: %r -> %r -> %r" % (text, t.encode(text), back)
got = t.decode([195])
assert got == "�", "decode([195]) is half of 'é': it should not crash but give '\\ufffd' (use errors='replace'), got %r" % (got,)
