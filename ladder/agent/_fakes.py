"""Scripted stand-ins for a real LLM and a real clock. No network, no waiting."""


class FakeModel:
    """Answers with `replies` in order, one per call. `forever`: after the script
    runs out, keep answering this (a model stuck in a loop). Records a copy of
    every messages list it was sent in .seen. With a clock, each call "takes"
    `seconds` of fake time."""

    def __init__(self, replies, forever=None, clock=None, seconds=0):
        self.replies = list(replies)
        self.forever = forever
        self.clock = clock
        self.seconds = seconds
        self.seen = []

    def __call__(self, messages):
        self.seen.append([dict(m) for m in messages])
        if self.clock is not None:
            self.clock.now += self.seconds
        if self.replies:
            return self.replies.pop(0)
        if self.forever is not None:
            assert len(self.seen) < 1000, (
                "the model was called 1000 times and run() still has not stopped: "
                "a model that never says final needs a step limit")
            return self.forever
        raise AssertionError(
            "the model was called %d times but the test only scripted %d replies: "
            "run() should stop at the first {'final': ...} reply" % (len(self.seen), len(self.seen) - 1))


class FakeClock:
    """clock() returns .now; only the test moves it."""

    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now
