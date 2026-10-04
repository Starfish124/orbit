import gpt

assert hasattr(gpt, "Value"), "no class called Value yet"
a = gpt.Value(2.0)
b = gpt.Value(3.0)
assert a.data == 2.0, "Value(2.0).data should be 2.0, got %r" % (getattr(a, "data", None),)
c = a + b
assert isinstance(c, gpt.Value), "a + b should give back a NEW Value, got %r" % (c,)
assert c.data == 5.0, "Value(2) + Value(3) should hold 5.0, got %r" % (c.data,)
d = a * b
assert isinstance(d, gpt.Value) and d.data == 6.0, "Value(2) * Value(3) should be a Value holding 6.0, got %r" % (getattr(d, "data", d),)
e = a * b + gpt.Value(1.0)
assert e.data == 7.0, "a * b + Value(1) should hold 7.0, got %r" % (e.data,)
assert a.data == 2.0 and b.data == 3.0, "a + b and a * b must not change a or b"
assert (a + 1).data == 3.0, "Value + plain number should work: wrap the number in a Value first"
assert (a * 4).data == 8.0, "Value * plain number should work: Value(2) * 4 is 8.0"

assert hasattr(gpt, "numeric_derivative"), "no function numeric_derivative yet"
got = gpt.numeric_derivative(lambda x: x * x, 3.0)
assert abs(got - 6.0) < 1e-3, "the slope of x*x at 3 is 6, your numeric_derivative gave %r" % (got,)
got = gpt.numeric_derivative(lambda x: x ** 3, 2.0)
assert abs(got - 12.0) < 1e-3, "the slope of x**3 at 2 is 12, got %r" % (got,)
got = gpt.numeric_derivative(lambda x: x * x, 3.0, h=0.5)
assert abs(got - 6.5) < 1e-9, "with h=0.5 the formula (f(x+h) - f(x)) / h gives exactly 6.5 for x*x at 3, got %r: use the h you are given" % (got,)
got = gpt.numeric_derivative(lambda x: (gpt.Value(x) * gpt.Value(x) + gpt.Value(x) * 2).data, 1.0)
assert abs(got - 4.0) < 1e-3, "the slope of x*x + 2x at 1 is 4 (built from Values), got %r" % (got,)
