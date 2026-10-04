import math

import gpt

V = gpt.Value
for name in ["exp", "log", "tanh"]:
    assert callable(getattr(V(1.0), name, None)), "no %s() method on Value yet" % name
try:
    V(2.0) ** 3
except TypeError:
    raise AssertionError("Value ** 3 does not work yet: add __pow__")
try:
    V(1.0) / V(2.0)
except TypeError:
    raise AssertionError("Value / Value does not work yet: add __truediv__")

assert abs((V(2.0) ** 3).data - 8.0) < 1e-12, "Value(2) ** 3 should be 8"
assert abs(V(1.0).exp().data - math.e) < 1e-12, "Value(1).exp() should be e = 2.718..."
assert abs(V(math.e).log().data - 1.0) < 1e-12, "Value(e).log() should be 1"
assert abs(V(0.5).tanh().data - math.tanh(0.5)) < 1e-12, "Value(0.5).tanh() should match math.tanh(0.5)"
assert abs((V(3.0) / V(4.0)).data - 0.75) < 1e-12, "Value(3) / Value(4) should be 0.75"
assert abs((V(3.0) / 4).data - 0.75) < 1e-12, "Value(3) / 4 should be 0.75"
assert abs((1 / V(4.0)).data - 0.25) < 1e-12, "1 / Value(4) should be 0.25: add __rtruediv__"


def slope(f, x, h=1e-5):
    return (f(V(x + h)).data - f(V(x - h)).data) / (2 * h)


cases = [
    ("x ** 3", lambda x: x ** 3, 1.5),
    ("x ** -1", lambda x: x ** -1, 2.0),
    ("x ** 0.5", lambda x: x ** 0.5, 4.0),
    ("x.exp()", lambda x: x.exp(), 0.3),
    ("x.log()", lambda x: x.log(), 2.5),
    ("x.tanh()", lambda x: x.tanh(), 0.7),
    ("3 / x", lambda x: 3 / x, 2.0),
    ("x / (x + 1)", lambda x: x / (x + 1), 2.0),
    ("(x*x + 1).log() * x.tanh() / (x.exp() + 2)", lambda x: (x * x + 1).log() * x.tanh() / (x.exp() + 2), 0.7),
]
for name, f, x0 in cases:
    x = V(x0)
    f(x).backward()
    want = slope(f, x0)
    assert abs(x.grad - want) < 1e-4, "d/dx of %s at %s: nudging x says %.6f, your backward() says %r" % (name, x0, want, x.grad)
