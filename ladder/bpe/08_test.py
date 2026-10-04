import os
import bpe

EOT = "<|endoftext|>"
t = bpe.Tokenizer()
assert hasattr(t, "save") and hasattr(t, "load"), "no save/load methods yet"
text = ("the quick brown fox jumps over the lazy dog. the dog sleeps; the fox runs. "
        "it's 2024 and the fox's den is café-warm 👋 ") * 3
t.train(text, 320)
t.add_special(EOT, 5000)
path = "tok.json"
t.save(path)
assert os.path.exists(path), "save('tok.json') should create the file"
t2 = bpe.Tokenizer()
t2.train("something else entirely", 270)
t2.load(path)
assert t2.merges == t.merges, "loaded merges differ from the saved ones"
assert list(t2.merges.items()) == list(t.merges.items()), "loaded merges must keep the learned ORDER"
assert all(type(k) is tuple for k in t2.merges), "loaded merge keys must be tuples like (97, 98), not lists"
assert t2.vocab == t.vocab, "the loaded vocab should match: rebuild it from the merges"
for s in ["the fox", "the dog sleeps" + EOT + "café 👋🏽", "brand new words", EOT, ""]:
    a, b = t.encode(s), t2.encode(s)
    assert a == b, "loaded tokenizer encodes %r as %r, the original gave %r" % (s, b, a)
    assert t2.decode(b) == s, "loaded tokenizer's round trip broke on %r" % (s,)
assert t2.encode(EOT) == [5000], "special tokens must survive save/load"
os.remove(path)
