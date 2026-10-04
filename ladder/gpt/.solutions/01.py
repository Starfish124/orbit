def numeric_derivative(f, x, h=1e-6):
    return (f(x + h) - f(x)) / h


class Value:
    def __init__(self, data):
        self.data = data

    def __add__(self, other):
        if not isinstance(other, Value):
            other = Value(other)
        return Value(self.data + other.data)

    def __mul__(self, other):
        if not isinstance(other, Value):
            other = Value(other)
        return Value(self.data * other.data)
