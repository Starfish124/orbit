import re
import bpe

assert hasattr(bpe, "SPLIT"), "no SPLIT pattern at the top of bpe.py yet"
assert bpe.train("aaabdaaabac", 259) == {(97, 97): 256, (256, 97): 257, (257, 98): 258}, "the train function from stage 4 must stay as it was"
got = re.findall(bpe.SPLIT, "hello world")
assert got == ["hello", " world"], "re.findall(SPLIT, 'hello world') should be ['hello', ' world'], got %r" % (got,)
sample = "It's 2024!  Hi,   there\nnew line 👋 café"
assert "".join(re.findall(bpe.SPLIT, sample)) == sample, "SPLIT must not lose any characters: joining the pieces should give the text back"
t = bpe.Tokenizer()
t.train("ab ab ab ab", 262)
assert t.merges == {(97, 98): 256, (32, 256): 257}, (
    "training on 'ab ab ab ab' in chunks ['ab', ' ab', ' ab', ' ab'] should learn exactly "
    "{(97, 98): 256, (32, 256): 257} and then run out of pairs. Got %r" % (t.merges,))
for i, tok in t.vocab.items():
    assert b" " not in tok[1:], "token %d is %r: a merge crossed a word boundary (a space after the first byte)" % (i, tok)
got = t.encode("ab ab")
assert got == [256, 257], "encode('ab ab') should be [256, 257], got %r" % (got,)
t = bpe.Tokenizer()
t.train("the cat sat on the mat. the cat ate the rat, then the cat sat.", 300)
for i, tok in t.vocab.items():
    assert b" " not in tok[1:], "token %d is %r: a merge crossed a word boundary" % (i, tok)
for text in ["the cat", "héllo wörld", "👋🏽 hi", "a  b\n", ""]:
    back = t.decode(t.encode(text))
    assert back == text, "round trip broke: %r -> %r" % (text, back)
try:
    t.train("abc", 10)
except ValueError:
    pass
else:
    raise AssertionError("Tokenizer.train with vocab_size below 256 should raise ValueError")
