import math
import random

import gpt

assert hasattr(gpt, "Bigram"), "no class called Bigram yet"
words = ["ava", "emma", "anna", "ada"]
m = gpt.Bigram(words, random.Random(0))
assert m.vocab == [".", "a", "d", "e", "m", "n", "v"], 'vocab should be "." then the sorted letters, got %r' % (m.vocab,)
assert m.stoi == {c: i for i, c in enumerate(m.vocab)}, "stoi should map each character to its index in vocab"
assert len(m.table) == 7 and all(len(row) == 7 for row in m.table), "table should be 7 rows of 7 Values (one row per previous character)"
assert len(m.parameters()) == 49, "parameters() should list all 49 table Values"
assert len(set(p.data for p in m.parameters())) > 1, "start the table at small random numbers from rng.uniform(-0.1, 0.1)"


def expected_loss(model):
    total, count = 0.0, 0
    for w in words:
        chars = ["."] + list(w) + ["."]
        for a, b in zip(chars, chars[1:]):
            row = [v.data for v in model.table[model.stoi[a]]]
            top = max(row)
            total += math.log(sum(math.exp(x - top) for x in row)) - (row[model.stoi[b]] - top)
            count += 1
    return total / count


loss = m.loss(words)
assert isinstance(loss, gpt.Value), "loss(words) should return a Value"
assert abs(loss.data - expected_loss(m)) < 1e-9, "loss should be the mean cross_entropy over every pair in '.ava.' etc. = %r, got %r" % (expected_loss(m), loss.data)
assert abs(loss.data - math.log(7)) < 0.1, "an untrained model should be about log(7) = 1.95, got %r" % loss.data

losses = m.train(words, 40, 5.0)
assert len(losses) == 40, "train(words, 40, lr) should return 40 losses, got %d" % len(losses)
assert losses[-1] < 0.9, "after 40 steps at lr 5.0 the loss should be below 0.9, got %.3f" % losses[-1]

s = m.sample(random.Random(3))
assert isinstance(s, str), "sample should return a string, got %r" % (s,)
assert s == m.sample(random.Random(3)), "the same seed should give the same sample: use the rng you are given"
assert "." not in s and set(s) <= set(m.vocab), "a sample should use only vocab letters and never include the '.', got %r" % s
assert len(m.sample(random.Random(4), max_len=2)) <= 2, "max_len=2 should cap the sample at 2 letters"
names = [m.sample(random.Random(i)) for i in range(20)]
assert len(set(names)) > 1, "20 seeds all gave %r: sample should be random at temperature 1" % names[0]

greedy, i = "", 0
while len(greedy) < 20:
    row = [v.data for v in m.table[i]]
    i = row.index(max(row))
    if i == 0:
        break
    greedy += m.vocab[i]
cold = m.sample(random.Random(5), temperature=0.01)
assert cold == greedy, "at temperature 0.01 the model should always pick its top choice, giving %r, got %r: divide the logits by temperature" % (greedy, cold)
try:
    m.sample(random.Random(0), temperature=0)
except ValueError:
    pass
else:
    raise AssertionError("temperature=0 should raise ValueError (you would divide by zero)")
