import random

import gpt

assert hasattr(gpt, "Linear"), "no class called Linear yet"
assert hasattr(gpt, "fit"), "no function called fit yet"

layer = gpt.Linear(3, 2, random.Random(0))
assert len(layer.w) == 2 and all(len(row) == 3 for row in layer.w), "Linear(3, 2, rng).w should be 2 rows of 3 weights"
assert len(layer.b) == 2, "Linear(3, 2, rng).b should hold 2 biases"
assert all(isinstance(p, gpt.Value) for p in layer.parameters()), "every weight and bias should be a Value"
assert len(layer.parameters()) == 8, "Linear(3, 2) has 6 weights + 2 biases = 8 parameters, got %d" % len(layer.parameters())
again = gpt.Linear(3, 2, random.Random(0))
assert [p.data for p in again.parameters()] == [p.data for p in layer.parameters()], "same seed should give the same weights: use the rng you are given, not random.uniform"
assert len(set(p.data for p in layer.parameters())) > 2, "the weights should be random numbers from rng.uniform(-1, 1)"

out = layer([1.0, 2.0, 3.0])
assert isinstance(out, list) and len(out) == 2, "layer(x) should return a list of 2 Values"
for j in range(2):
    want = layer.b[j].data + sum(w.data * x for w, x in zip(layer.w[j], [1.0, 2.0, 3.0]))
    assert abs(out[j].data - want) < 1e-9, "output %d should be b[%d] + sum of w[%d][i] * x[i] = %r, got %r" % (j, j, j, want, out[j].data)

xs = [[a, b] for a in (-1.0, 0.0, 1.0) for b in (-1.0, 0.5, 1.0)]
ys = [[2 * a - 3 * b + 1] for a, b in xs]

m = gpt.Linear(2, 1, random.Random(2))
first = sum((m(x)[0].data - y[0]) ** 2 for x, y in zip(xs, ys)) / len(xs)
got = gpt.fit(m, xs, ys, 1, 0.0)
assert isinstance(got, list) and len(got) == 1, "fit(..., steps=1, ...) should return a list with 1 loss"
assert abs(got[0] - first) < 1e-9, "the loss should be the mean of (prediction - target)**2 = %r, got %r" % (first, got[0])
g1 = [p.grad for p in m.parameters()]
gpt.fit(m, xs, ys, 1, 0.0)
g2 = [p.grad for p in m.parameters()]
assert all(abs(a - b) < 1e-9 for a, b in zip(g1, g2)), "the same step twice gave different grads %r then %r: set every p.grad = 0 before backward()" % (g1, g2)

m = gpt.Linear(2, 1, random.Random(1))
losses = gpt.fit(m, xs, ys, 60, 0.1)
assert len(losses) == 60, "fit(..., steps=60, ...) should return 60 losses, got %d" % len(losses)
assert losses[-1] < losses[0], "the loss should go down: first %.4f, last %.4f" % (losses[0], losses[-1])
assert losses[-1] < 0.01, "after 60 steps at lr 0.1 the loss should be below 0.01, got %.4f: step AGAINST the gradient, p.data -= lr * p.grad" % losses[-1]
w = [p.data for p in m.parameters()]
assert abs(w[0] - 2) < 0.1 and abs(w[1] + 3) < 0.1 and abs(w[2] - 1) < 0.1, "it should have learned y = 2a - 3b + 1, got weights %r" % (w,)
