import math

import gpt

V = gpt.Value
assert hasattr(gpt, "softmax"), "no function called softmax yet"
assert hasattr(gpt, "cross_entropy"), "no function called cross_entropy yet"

logits = [V(1.0), V(2.0), V(3.0)]
probs = gpt.softmax(logits)
assert isinstance(probs, list) and len(probs) == 3, "softmax of 3 logits should return a list of 3"
assert all(isinstance(p, gpt.Value) for p in probs), "softmax should return Values so gradients can flow through it"
e = [math.exp(x) for x in (1, 2, 3)]
want = [x / sum(e) for x in e]
got = [p.data for p in probs]
assert all(abs(a - b) < 1e-9 for a, b in zip(got, want)), "softmax([1, 2, 3]) should be %r, got %r" % (want, got)
assert abs(sum(got) - 1) < 1e-9, "probabilities should sum to 1, got %r" % sum(got)

try:
    big = [p.data for p in gpt.softmax([V(1000.0), V(1001.0)])]
except OverflowError:
    raise AssertionError("softmax([1000, 1001]) overflowed: exp(1000) is too big for a float. Subtract the biggest logit first")
want = [1 / (1 + math.e), math.e / (1 + math.e)]
assert all(abs(a - b) < 1e-9 for a, b in zip(big, want)), "softmax([1000, 1001]) should be %r, got %r" % (want, big)

logits = [V(0.5), V(-1.0), V(2.0), V(0.0)]
loss = gpt.cross_entropy(logits, 2)
assert isinstance(loss, gpt.Value), "cross_entropy should return a Value"
e = [math.exp(x) for x in (0.5, -1.0, 2.0, 0.0)]
p = [x / sum(e) for x in e]
assert abs(loss.data + math.log(p[2])) < 1e-9, "cross_entropy(logits, 2) should be -log(p[2]) = %r, got %r" % (-math.log(p[2]), loss.data)
loss.backward()
for i in range(4):
    want = p[i] - (1 if i == 2 else 0)
    assert abs(logits[i].grad - want) < 1e-9, "logit %d grad should be p[%d] - (1 if it is the target) = %r, got %r" % (i, i, want, logits[i].grad)

try:
    far = gpt.cross_entropy([V(0.0), V(1000.0)], 0).data
except (ValueError, OverflowError, ZeroDivisionError):
    raise AssertionError("cross_entropy([0, 1000], 0) crashed: the target's probability rounds to 0 and log(0) fails. Use log(sum(exp(v - max))) - (logit[target] - max)")
assert abs(far - 1000) < 1e-6, "cross_entropy([0, 1000], 0) should be about 1000, got %r" % (far,)
