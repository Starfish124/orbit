"""A pretend internet for the crawler tests. No network: fetch looks pages up in a dict."""
import asyncio
import threading
import time

HOST = "http://x.com"


def u(path):
    return HOST + path


def short(urls):
    """{'http://x.com/a', ...} -> ['/a', ...] so messages stay readable."""
    return sorted(x.replace(HOST, "") for x in urls)


class FakeWeb:
    """pages = {url: [links]}. fail = {url: how many times it fails before it works}.
    slow = urls whose async fetch takes 3 s (only a timeout gets past them).
    Records every fetch in .calls and the most fetches ever running at once in .max_active."""

    def __init__(self, pages, delay=0, fail=None, slow=()):
        self.pages = pages
        self.delay = delay
        self.fail = dict(fail or {})
        self.slow = set(slow)
        self.calls = []
        self.cancelled = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def _start(self, url):
        with self.lock:
            self.calls.append(url)
            self.active += 1
            self.max_active = max(self.max_active, self.active)

    def _answer(self, url):
        with self.lock:
            self.active -= 1
            if self.fail.get(url, 0) > 0:
                self.fail[url] -= 1
                raise ConnectionError("connection reset while fetching " + url)
        if url not in self.pages:
            raise LookupError("404 not found: " + url)
        return list(self.pages[url])

    def fetch(self, url):
        self._start(url)
        time.sleep(self.delay)
        return self._answer(url)

    async def afetch(self, url):
        self._start(url)
        try:
            await asyncio.sleep(3 if url in self.slow else self.delay)
        except asyncio.CancelledError:
            with self.lock:
                self.active -= 1
            self.cancelled.append(url)
            raise
        return self._answer(url)

    def twice(self):
        return short({x for x in self.calls if self.calls.count(x) > 1})


def star(n):
    """The start page links to n-1 pages; each of them links back (a cycle)."""
    pages = {u("/"): [u("/p%d" % i) for i in range(1, n)]}
    for i in range(1, n):
        pages[u("/p%d" % i)] = [u("/")]
    return pages


def messy():
    """Relative links, #fragments, another host, cycles. No broken pages."""
    return {
        u("/"): ["a", "/b#top", "http://y.com/away", "#self"],
        u("/a"): ["/b", "c/"],
        u("/b"): ["/", "a#x", "http://y.com/"],
        u("/c/"): ["d", "../b"],
        u("/c/d"): ["/c/#end"],
    }


MESSY = {u("/"), u("/a"), u("/b"), u("/c/"), u("/c/d")}
