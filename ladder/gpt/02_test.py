import gpt

V = gpt.Value
assert hasattr(V(1.0), "grad"), "a Value has no .grad yet: start it at 0 in __init__"
assert V(1.0).grad == 0, "a new Value's grad should start at 0, got %r" % (V(1.0).grad,)
assert callable(getattr(V(1.0), "backward", None)), "no backward() method yet"

a, b, c = V(2.0), V(-3.0), V(10.0)
d = a * b + c
d.backward()
assert d.grad == 1, "backward() should set the output's own grad to 1, got %r" % (d.grad,)
assert (a.grad, b.grad, c.grad) == (-3.0, 2.0, 1.0), \
    "for d = a*b + c: expected grads a=-3 (=b), b=2 (=a), c=1, got a=%r b=%r c=%r" % (a.grad, b.grad, c.grad)

x = V(3.0)
y = x * x
y.backward()
assert x.grad == 6.0, "y = x*x at 3 should give x.grad 6, got %r: x is used twice, so grads must ADD (+=), not overwrite (=)" % (x.grad,)

x = V(2.0)
p = x * 3
q = x * p
out = p + q                      # 3x + 3x*x, slope 3 + 6x = 15 at x=2
out.backward()
assert x.grad == 15.0, "out = 3x + 3x*x at 2 should give x.grad 15, got %r: each node must run its backward only after everything that uses it (topological order)" % (x.grad,)
assert p.grad == 1.0 + 2.0, "p feeds out directly (1) and through q = x*p (x = 2): p.grad should be 3, got %r" % (p.grad,)

a = V(4.0)
assert (2 + a).data == 6.0, "2 + Value(4) should work: add __radd__"
assert (2 * a).data == 8.0, "2 * Value(4) should work: add __rmul__"
assert (-a).data == -4.0, "-Value(4) should be -4: add __neg__"
assert (a - 1).data == 3.0 and (a - V(1.0)).data == 3.0, "Value(4) - 1 should be 3: add __sub__"
assert (10 - a).data == 6.0, "10 - Value(4) should be 6: add __rsub__"

a, b = V(4.0), V(5.0)
out = 7 - a * b + 2 * a
out.backward()
assert (a.grad, b.grad) == (-3.0, -4.0), \
    "out = 7 - a*b + 2a: expected a.grad = -b + 2 = -3 and b.grad = -a = -4, got %r and %r" % (a.grad, b.grad)
