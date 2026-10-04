import math


def numeric_derivative(f, x, h=1e-6):
    return (f(x + h) - f(x)) / h


class Value:
    def __init__(self, data, children=()):
        self.data = data
        self.grad = 0
        self._prev = children
        self._backward = lambda: None

    def __repr__(self):
        return "Value(%r)" % self.data

    def __add__(self, other):
        if not isinstance(other, Value):
            other = Value(other)
        out = Value(self.data + other.data, (self, other))

        def _backward():
            self.grad += out.grad
            other.grad += out.grad
        out._backward = _backward
        return out

    def __mul__(self, other):
        if not isinstance(other, Value):
            other = Value(other)
        out = Value(self.data * other.data, (self, other))

        def _backward():
            self.grad += other.data * out.grad
            other.grad += self.data * out.grad
        out._backward = _backward
        return out

    def __pow__(self, n):
        out = Value(self.data ** n, (self,))

        def _backward():
            self.grad += n * self.data ** (n - 1) * out.grad
        out._backward = _backward
        return out

    def exp(self):
        out = Value(math.exp(self.data), (self,))

        def _backward():
            self.grad += out.data * out.grad
        out._backward = _backward
        return out

    def log(self):
        out = Value(math.log(self.data), (self,))

        def _backward():
            self.grad += (1 / self.data) * out.grad
        out._backward = _backward
        return out

    def tanh(self):
        t = math.tanh(self.data)
        out = Value(t, (self,))

        def _backward():
            self.grad += (1 - t * t) * out.grad
        out._backward = _backward
        return out

    def __radd__(self, other):
        return self + other

    def __rmul__(self, other):
        return self * other

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return (-self) + other

    def __truediv__(self, other):
        return self * other ** -1

    def __rtruediv__(self, other):
        return other * self ** -1

    def backward(self):
        order = []
        seen = set()

        def visit(v):
            if v not in seen:
                seen.add(v)
                for child in v._prev:
                    visit(child)
                order.append(v)
        visit(self)
        self.grad = 1
        for v in reversed(order):
            v._backward()


class Linear:
    def __init__(self, nin, nout, rng):
        self.w = [[Value(rng.uniform(-1, 1)) for _ in range(nin)] for _ in range(nout)]
        self.b = [Value(0) for _ in range(nout)]

    def __call__(self, x):
        out = []
        for row, bias in zip(self.w, self.b):
            total = bias
            for wi, xi in zip(row, x):
                total = total + wi * xi
            out.append(total)
        return out

    def parameters(self):
        params = []
        for row in self.w:
            params.extend(row)
        params.extend(self.b)
        return params


def fit(model, xs, ys, steps, lr):
    losses = []
    for _ in range(steps):
        total = 0
        count = 0
        for x, y in zip(xs, ys):
            for p, target in zip(model(x), y):
                total = total + (p - target) ** 2
                count += 1
        loss = total / count
        for p in model.parameters():
            p.grad = 0
        loss.backward()
        for p in model.parameters():
            p.data -= lr * p.grad
        losses.append(loss.data)
    return losses


def softmax(logits):
    biggest = max(v.data for v in logits)
    exps = [(v - biggest).exp() for v in logits]
    total = sum(exps)
    return [e / total for e in exps]


def cross_entropy(logits, target):
    biggest = max(v.data for v in logits)
    total = sum((v - biggest).exp() for v in logits)
    return total.log() - (logits[target] - biggest)


def pick(logits, rng, temperature):
    if temperature <= 0:
        raise ValueError("temperature must be above 0")
    probs = softmax([Value(v.data / temperature) for v in logits])
    weights = [p.data for p in probs]
    return rng.choices(range(len(weights)), weights=weights)[0]


class Bigram:
    def __init__(self, words, rng):
        self.vocab = ["."] + sorted(set("".join(words)))
        self.stoi = {ch: i for i, ch in enumerate(self.vocab)}
        n = len(self.vocab)
        self.table = [[Value(rng.uniform(-0.1, 0.1)) for _ in range(n)] for _ in range(n)]

    def parameters(self):
        params = []
        for row in self.table:
            params.extend(row)
        return params

    def loss(self, words):
        total = 0
        count = 0
        for word in words:
            chars = ["."] + list(word) + ["."]
            for a, b in zip(chars, chars[1:]):
                total = total + cross_entropy(self.table[self.stoi[a]], self.stoi[b])
                count += 1
        return total / count

    def train(self, words, steps, lr):
        losses = []
        for _ in range(steps):
            loss = self.loss(words)
            for p in self.parameters():
                p.grad = 0
            loss.backward()
            for p in self.parameters():
                p.data -= lr * p.grad
            losses.append(loss.data)
        return losses

    def sample(self, rng, temperature=1.0, max_len=20):
        out = ""
        i = 0
        while len(out) < max_len:
            i = pick(self.table[i], rng, temperature)
            if i == 0:
                break
            out += self.vocab[i]
        return out


class Attention:
    def __init__(self, n_embd, rng):
        self.n_embd = n_embd
        self.q = Linear(n_embd, n_embd, rng)
        self.k = Linear(n_embd, n_embd, rng)
        self.v = Linear(n_embd, n_embd, rng)
        self.weights = []

    def __call__(self, xs):
        qs = [self.q(x) for x in xs]
        ks = [self.k(x) for x in xs]
        vs = [self.v(x) for x in xs]
        scale = 1 / math.sqrt(self.n_embd)
        outs = []
        self.weights = []
        for t in range(len(xs)):
            scores = []
            for s in range(t + 1):
                dot = sum(a * b for a, b in zip(qs[t], ks[s]))
                scores.append(dot * scale)
            w = softmax(scores)
            self.weights.append([p.data for p in w])
            out = []
            for d in range(self.n_embd):
                out.append(sum(w[s] * vs[s][d] for s in range(t + 1)))
            outs.append(out)
        return outs

    def parameters(self):
        return self.q.parameters() + self.k.parameters() + self.v.parameters()


class GPT:
    def __init__(self, vocab_size, block_size, n_embd, rng):
        self.vocab_size = vocab_size
        self.block_size = block_size
        self.wte = [[Value(rng.uniform(-1, 1)) for _ in range(n_embd)] for _ in range(vocab_size)]
        self.wpe = [[Value(rng.uniform(-1, 1)) for _ in range(n_embd)] for _ in range(block_size)]
        self.attn = Attention(n_embd, rng)
        self.fc1 = Linear(n_embd, 4 * n_embd, rng)
        self.fc2 = Linear(4 * n_embd, n_embd, rng)
        self.lm_head = Linear(n_embd, vocab_size, rng)

    def parameters(self):
        params = []
        for row in self.wte + self.wpe:
            params.extend(row)
        for layer in [self.attn, self.fc1, self.fc2, self.lm_head]:
            params.extend(layer.parameters())
        return params

    def __call__(self, tokens):
        if len(tokens) > self.block_size:
            raise ValueError("at most block_size tokens")
        xs = []
        for t, tok in enumerate(tokens):
            xs.append([a + b for a, b in zip(self.wte[tok], self.wpe[t])])
        att = self.attn(xs)
        xs = [[a + b for a, b in zip(x, y)] for x, y in zip(xs, att)]
        logits = []
        for x in xs:
            h = [v.tanh() for v in self.fc1(x)]
            x = [a + b for a, b in zip(x, self.fc2(h))]
            logits.append(self.lm_head(x))
        return logits

    def loss(self, tokens):
        logits = self(tokens[:-1])
        total = 0
        for row, target in zip(logits, tokens[1:]):
            total = total + cross_entropy(row, target)
        return total / len(logits)

    def train(self, tokens, steps, lr):
        losses = []
        for _ in range(steps):
            loss = self.loss(tokens)
            for p in self.parameters():
                p.grad = 0
            loss.backward()
            for p in self.parameters():
                p.data -= lr * p.grad
            losses.append(loss.data)
        return losses

    def generate(self, tokens, n, rng, temperature=1.0):
        out = list(tokens)
        for _ in range(n):
            logits = self(out[-self.block_size:])
            out.append(pick(logits[-1], rng, temperature))
        return out
