import bpe

EOT = "<|endoftext|>"
t = bpe.Tokenizer()
assert hasattr(t, "add_special"), "no method add_special yet"
assert len(t.encode(EOT)) > 1, "before add_special, '<|endoftext|>' is just ordinary text (many ids)"
t.train("ab ab ab ab", 262)
assert t.merges == {(97, 98): 256, (32, 256): 257}, "training from stage 6 broke: %r" % (t.merges,)
t.add_special(EOT, 1000)
got = t.encode(EOT)
assert got == [1000], "encode('<|endoftext|>') should be [1000], got %r" % (got,)
got = t.encode("ab" + EOT + " ab")
assert got == [256, 1000, 257], "encode('ab<|endoftext|> ab') should be [256, 1000, 257], got %r" % (got,)
got = t.encode(EOT + EOT)
assert got == [1000, 1000], "two special tokens in a row should be [1000, 1000], got %r" % (got,)
assert t.decode([256, 1000, 257]) == "ab" + EOT + " ab", "decode should turn 1000 back into '<|endoftext|>', got %r" % (t.decode([256, 1000, 257]),)
t.add_special("<|pad|>", 1001)
text = "hi<|pad|>there" + EOT + "a<b>|c 👋"
back = t.decode(t.encode(text))
assert back == text, "round trip with two special tokens broke: %r" % (back,)
assert t.encode("<|pad|>")  == [1001], "second special token should encode to [1001]"
assert 1000 not in t.encode("<|endoftext"), "an unfinished special token is ordinary text"
for bad in [256, 1000]:
    try:
        t.add_special("<|x|>", bad)
    except ValueError:
        pass
    else:
        raise AssertionError("add_special with id %d should raise ValueError: that id is already taken" % bad)
