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
