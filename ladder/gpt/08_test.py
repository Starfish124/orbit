import math
import random

import gpt

assert hasattr(gpt, "GPT"), "no class called GPT yet"
g = gpt.GPT(5, 4, 4, random.Random(0))
assert len(g.wte) == 5 and all(len(r) == 4 for r in g.wte), "wte should be 5 rows (one per token) of 4 Values"
assert len(g.wpe) == 4 and all(len(r) == 4 for r in g.wpe), "wpe should be 4 rows (one per position) of 4 Values"
assert isinstance(g.attn, gpt.Attention), "g.attn should be an Attention(4, rng)"
assert len(g.fc1.w) == 16 and len(g.fc2.w) == 4 and len(g.fc2.w[0]) == 16, "the MLP is fc1 = Linear(4, 16) then fc2 = Linear(16, 4)"
assert len(g.lm_head.w) == 5, "lm_head should be Linear(4, 5): one logit per token"
assert len(g.parameters()) == 269, "wte 20 + wpe 16 + attn 60 + fc1 80 + fc2 68 + lm_head 25 = 269 parameters, got %d" % len(g.parameters())

logits = g([1, 2, 3])
assert len(logits) == 3 and all(len(r) == 5 for r in logits), "g([1, 2, 3]) should give 3 rows of 5 logits"
assert all(isinstance(x, gpt.Value) for r in logits for x in r), "logits should be Values"
try:
    g([1, 2, 3, 4, 0])
except ValueError:
    pass
else:
    raise AssertionError("5 tokens with block_size 4 should raise ValueError")
a = g([1, 2, 3, 4])
b = g([1, 2, 3, 0])
for t in range(3):
    assert [x.data for x in a[t]] == [x.data for x in b[t]], "changing the last token changed the logits at position %d: the model sees the future" % t

z = gpt.GPT(5, 4, 4, random.Random(3))
for p in z.attn.parameters() + z.fc2.parameters():
    p.data = 0.0
got = [[x.data for x in r] for r in z([2, 0, 4])]
for t, tok in enumerate([2, 0, 4]):
    x = [e.data + p.data for e, p in zip(z.wte[tok], z.wpe[t])]
    want = [b.data + sum(w.data * xi for w, xi in zip(row, x)) for row, b in zip(z.lm_head.w, z.lm_head.b)]
    assert all(abs(u - v) < 1e-9 for u, v in zip(got[t], want)), "with attention and fc2 zeroed, logits should be lm_head(wte[token] + wpe[position]): keep the residuals, x = x + attn(x) and x = x + mlp(x)"

seq = [1, 2, 3, 4, 1]
rows = [[x.data for x in r] for r in g(seq[:-1])]
want = sum(math.log(sum(math.exp(v) for v in r)) - r[tgt] for r, tgt in zip(rows, seq[1:])) / 4
loss = g.loss(seq)
assert abs(loss.data - want) < 1e-9, "loss([1,2,3,4,1]) should be the mean cross_entropy of each position predicting the next token = %r, got %r" % (want, loss.data)

losses = g.train(seq, 30, 0.15)
assert len(losses) == 30 and losses[-1] < losses[0], "train should return 30 losses going down, first %r last %r" % (losses[0], losses[-1])
assert losses[-1] < 0.3, "after 30 steps at lr 0.15 the loss should be below 0.3, got %.3f" % losses[-1]

out = g.generate([1], 4, random.Random(0), temperature=0.01)
assert out == [1, 2, 3, 4, 1], "trained on 1 2 3 4 1, greedy generate([1], 4) should continue 1 -> 2 3 4 1, got %r" % (out,)
try:
    long = g.generate([1], 10, random.Random(7))
except ValueError:
    raise AssertionError("generate crashed past block_size: feed the model only the last block_size tokens, out[-block_size:]")
assert len(long) == 11 and long[0] == 1, "generate([1], 10, ...) should return the prompt plus 10 new tokens, got %r" % (long,)
assert all(isinstance(t, int) and 0 <= t < 5 for t in long), "generated tokens should be ints in 0..4, got %r" % (long,)
assert long == g.generate([1], 10, random.Random(7)), "the same seed should generate the same tokens"
