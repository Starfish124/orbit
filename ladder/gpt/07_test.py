import math
import random

import gpt

assert hasattr(gpt, "Attention"), "no class called Attention yet"
att = gpt.Attention(4, random.Random(0))
for name in ["q", "k", "v"]:
    lin = getattr(att, name, None)
    assert isinstance(lin, gpt.Linear) and len(lin.w) == 4 and len(lin.w[0]) == 4, "att.%s should be a Linear(4, 4)" % name
assert len(att.parameters()) == 60, "q, k and v each have 16 weights + 4 biases: 60 parameters, got %d" % len(att.parameters())

rng = random.Random(1)
xs = [[rng.uniform(-1, 1) for _ in range(4)] for _ in range(5)]
outs = att(xs)
assert isinstance(outs, list) and len(outs) == 5, "5 positions in should give 5 outputs, got %r" % (len(outs) if isinstance(outs, list) else outs,)
assert all(len(o) == 4 and all(isinstance(x, gpt.Value) for x in o) for o in outs), "each output should be a list of 4 Values"


def lin(layer, x):
    return [b.data + sum(w.data * xi for w, xi in zip(row, x)) for row, b in zip(layer.w, layer.b)]


qs, ks, vs = [lin(att.q, x) for x in xs], [lin(att.k, x) for x in xs], [lin(att.v, x) for x in xs]
w_rows = att.weights
assert len(w_rows) == 5, "att.weights should hold one row of attention weights per position, got %d rows" % len(w_rows)
for t in range(5):
    assert len(w_rows[t]) == t + 1, "position %d may only look at positions 0..%d, so its row should have %d weights, got %d" % (t, t, t + 1, len(w_rows[t]))
    assert abs(sum(w_rows[t]) - 1) < 1e-9, "position %d's weights should sum to 1, got %r" % (t, sum(w_rows[t]))
    scores = [sum(a * b for a, b in zip(qs[t], ks[s])) / math.sqrt(4) for s in range(t + 1)]
    e = [math.exp(x - max(scores)) for x in scores]
    want_w = [x / sum(e) for x in e]
    assert all(abs(a - b) < 1e-9 for a, b in zip(w_rows[t], want_w)), "position %d: weights should be softmax(q.k / sqrt(4)) = %r, got %r" % (t, want_w, w_rows[t])
    want = [sum(want_w[s] * vs[s][d] for s in range(t + 1)) for d in range(4)]
    got = [x.data for x in outs[t]]
    assert all(abs(a - b) < 1e-9 for a, b in zip(got, want)), "position %d's output should be the weighted sum of the v vectors = %r, got %r" % (t, want, got)

changed = [list(x) for x in xs]
changed[3] = [9.0, -9.0, 9.0, -9.0]
outs2 = att(changed)
for t in range(3):
    assert [x.data for x in outs2[t]] == [x.data for x in outs[t]], "changing position 3 changed the output at position %d: a position must never see the future" % t
assert [x.data for x in outs2[3]] != [x.data for x in outs[3]], "changing position 3 should change position 3's own output"

total = sum(sum(o) for o in att(xs))
total.backward()
assert any(p.grad != 0 for p in att.q.parameters()), "gradients should flow back into the q weights: build the scores out of Values"
