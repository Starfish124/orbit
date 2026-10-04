"""Every stage's checks. Stage N's test runs check1..checkN, so earlier stages stay honest."""
import asyncio
import inspect
import time

import crawler
from _web import HOST, MESSY, FakeWeb, messy, short, star, u


def takes(fn, *names):
    params = inspect.signature(fn).parameters
    for name in names:
        assert name in params, "%s() should take an argument called %s" % (fn.__name__, name)


def check1():
    assert hasattr(crawler, "crawl"), "no function called crawl yet"
    web = FakeWeb({u("/"): [u("/a"), u("/b")], u("/a"): [u("/b"), u("/")],
                   u("/b"): [u("/a"), u("/c")], u("/c"): []})
    got = crawler.crawl(u("/"), web.fetch)
    assert isinstance(got, set), "crawl should return a set of URLs, got a %s" % type(got).__name__
    assert got == {u("/"), u("/a"), u("/b"), u("/c")}, \
        "crawl should find /, /a, /b, /c (the start page counts too), got %r" % short(got)
    assert not web.twice(), "each page should be fetched once, these were fetched more: %r (/a and /b link to each other: a cycle)" % web.twice()
    assert set(web.calls) == got, "every page found should be fetched once, fetched: %r" % short(web.calls)
    alone = FakeWeb({u("/"): []})
    got = crawler.crawl(u("/"), alone.fetch)
    assert got == {u("/")}, "a start page with no links: the result is just {start}, got %r" % short(got)


def depth_web():
    # / -> a, c    a -> b    b -> c    c -> d    d -> e      (levels: / 0, a c 1, b d 2, e 3)
    return FakeWeb({u("/"): [u("/a"), u("/c")], u("/a"): [u("/b")], u("/b"): [u("/c")],
                    u("/c"): [u("/d")], u("/d"): [u("/e")], u("/e"): []})


def check2():
    takes(crawler.crawl, "max_depth")
    web = depth_web()
    got = crawler.crawl(u("/"), web.fetch)
    assert got == {u(p) for p in ["/", "/a", "/b", "/c", "/d", "/e"]}, "no max_depth means no limit, got %r" % short(got)
    order = [x.replace(HOST, "") for x in web.calls]
    assert order == ["/", "/a", "/c", "/b", "/d", "/e"], \
        "pages should be fetched level by level (/, then /a /c, then /b /d, then /e), order was %r" % order
    web = depth_web()
    got = crawler.crawl(u("/"), web.fetch, max_depth=2)
    assert u("/e") not in got, "max_depth=2: /e is 3 clicks away and should not be in the result, got %r" % short(got)
    assert got == {u(p) for p in ["/", "/a", "/c", "/b", "/d"]}, \
        "max_depth=2 should give /, /a, /c (1 click) and /b, /d (2 clicks), got %r. /c is ONE click away: a crawl that goes deep first reaches it the long way and drops it" % short(got)
    assert short(web.calls) == ["/", "/a", "/c"], \
        "pages at depth 2 are found but never fetched (their links would be depth 3), fetched: %r" % short(web.calls)
    web = depth_web()
    got = crawler.crawl(u("/"), web.fetch, max_depth=0)
    assert got == {u("/")} and web.calls == [], "max_depth=0: just the start page and no fetch at all, got %r, fetched %r" % (short(got), short(web.calls))


def check3():
    assert hasattr(crawler, "normalize"), "no function called normalize yet"
    cases = [
        (("http://q.org/docs/intro", "setup"), "http://q.org/docs/setup"),
        (("http://q.org/docs/intro", "/faq#top"), "http://q.org/faq"),
        (("http://q.org/docs/intro", "#part2"), "http://q.org/docs/intro"),
        (("http://q.org/docs/", "../about"), "http://q.org/about"),
        (("http://q.org/", "http://other.net/x#y"), "http://other.net/x"),
    ]
    for args, want in cases:
        got = crawler.normalize(*args)
        assert got == want, "normalize%r should be %r, got %r" % (args, want, got)
    web = FakeWeb(messy())
    got = crawler.crawl(u("/"), web.fetch)
    assert got == MESSY, "crawl should resolve relative links, drop #fragments and stay on x.com: want %r, got %r" % (short(MESSY), short(got))
    assert not [x for x in web.calls if "y.com" in x], "y.com is another site: it must never be fetched"
    assert not web.twice(), "'/b#top' and '/b' are the same page: fetched twice: %r" % web.twice()
    got = crawler.crawl(u("/"), FakeWeb(messy()).fetch, max_depth=1)
    assert got == {u("/"), u("/a"), u("/b")}, "max_depth=1 on the messy site should give /, /a, /b, got %r" % short(got)


def broken_web(fail_flaky):
    return FakeWeb({u("/"): [u("/a"), u("/gone"), u("/flaky")], u("/a"): [u("/b")], u("/b"): [],
                    u("/flaky"): [u("/behind")], u("/behind"): []}, fail={u("/flaky"): fail_flaky})


def check4():
    takes(crawler.crawl, "errors", "retries")
    web = broken_web(1)
    try:
        got = crawler.crawl(u("/"), web.fetch)
    except Exception as e:
        raise AssertionError("fetch raised %s: %s -- crawl should note it and keep crawling, not crash" % (type(e).__name__, e))
    errors = {}
    got = crawler.crawl(u("/"), broken_web(1).fetch, errors=errors)
    assert got == {u(p) for p in ["/", "/a", "/b", "/gone", "/flaky"]}, \
        "failed pages still count as found (a link points to them), but /behind can't be seen: got %r" % short(got)
    assert set(errors) == {u("/gone"), u("/flaky")}, "errors should have exactly /gone and /flaky as keys, got %r" % short(errors)
    assert isinstance(errors[u("/gone")], LookupError), "errors[url] should be the exception fetch raised, got %r" % (errors[u("/gone")],)
    errors = {}
    web = broken_web(2)
    got = crawler.crawl(u("/"), web.fetch, errors=errors, retries=2)
    assert u("/behind") in got and set(errors) == {u("/gone")}, \
        "/flaky fails twice then works: with retries=2 it should succeed (errors: %r, found %r)" % (short(errors), short(got))
    assert web.calls.count(u("/gone")) == 3, "retries=2 means 3 tries in total for /gone, it was fetched %d times" % web.calls.count(u("/gone"))
    assert web.calls.count(u("/a")) == 1, "a page that works is fetched once, /a was fetched %d times" % web.calls.count(u("/a"))
    errors = {}
    crawler.crawl(u("/"), broken_web(2).fetch, errors=errors, retries=1)
    assert u("/flaky") in errors and isinstance(errors[u("/flaky")], ConnectionError), \
        "retries=1: /flaky fails both tries, errors should hold its last ConnectionError, got %r" % (errors,)


def check5():
    assert hasattr(crawler, "crawl_threaded"), "no function called crawl_threaded yet"
    pages = messy()
    pages[u("/a")] = pages[u("/a")] + ["/gone"]
    serial = crawler.crawl(u("/"), FakeWeb(pages).fetch)
    web = FakeWeb(pages)
    got = crawler.crawl_threaded(u("/"), web.fetch)
    assert got == serial, "crawl_threaded should find exactly what crawl finds: want %r, got %r" % (short(serial), short(got))
    assert not web.twice(), "fetched more than once: %r -- two threads both thought the page was new (see the lesson: who owns the set?)" % web.twice()
    # what a 0.03 s sleep really costs here: macOS coalesces timers, so on a
    # laptop it can take 0.1 s, and a fixed limit would fail correct code
    t = time.perf_counter()
    for _ in range(3):
        time.sleep(0.03)
    one = (time.perf_counter() - t) / 3
    web = FakeWeb(star(20), delay=0.03)
    t = time.perf_counter()
    got = crawler.crawl_threaded(u("/"), web.fetch, workers=8)
    took = time.perf_counter() - t
    assert len(got) == 20, "the star site has 20 pages, got %d" % len(got)
    assert 1 < web.max_active <= 8, "with workers=8, between 2 and 8 fetches should run at once, max was %d" % web.max_active
    assert took < 10 * one, "20 pages one by one take %.2f s here; 8 workers should take about a fifth of that, took %.2f s" % (20 * one, took)
    web = FakeWeb(star(6))
    crawler.crawl_threaded(u("/"), web.fetch, workers=1)
    assert web.max_active == 1, "workers=1 means one fetch at a time, saw %d at once" % web.max_active


def run_async(coro):
    return asyncio.run(coro)


def check6():
    assert hasattr(crawler, "crawl_async"), "no function called crawl_async yet"
    assert inspect.iscoroutinefunction(crawler.crawl_async), "crawl_async should be defined with `async def`"
    pages = messy()
    pages[u("/a")] = pages[u("/a")] + ["/gone"]
    serial = crawler.crawl(u("/"), FakeWeb(pages).fetch)
    web = FakeWeb(pages)
    got = run_async(crawler.crawl_async(u("/"), web.afetch))
    assert got == serial, "crawl_async should find exactly what crawl finds: want %r, got %r" % (short(serial), short(got))
    assert not web.twice(), "fetched more than once: %r" % web.twice()
    web = FakeWeb(star(20), delay=0.03)
    t = time.perf_counter()
    got = run_async(crawler.crawl_async(u("/"), web.afetch))
    took = time.perf_counter() - t
    assert len(got) == 20, "the star site has 20 pages, got %d" % len(got)
    assert web.max_active >= 10, "all 19 pages of one level should be fetched together (gather), max at once was %d" % web.max_active
    assert took < 0.25, "20 pages x 0.03 s is 0.6 s one by one; with gather it should take ~0.06 s, took %.2f s" % took


def check7():
    takes(crawler.crawl_async, "limit")
    web = FakeWeb(star(20), delay=0.01)
    got = run_async(crawler.crawl_async(u("/"), web.afetch, limit=3))
    assert len(got) == 20, "limit only slows things down, all 20 pages should be found, got %d" % len(got)
    assert web.max_active <= 3, "limit=3 but %d fetches ran at the same time" % web.max_active
    assert web.max_active == 3, "limit=3 should still run 3 at once (not one by one), max at once was %d" % web.max_active
    web = FakeWeb(star(8))
    run_async(crawler.crawl_async(u("/"), web.afetch, limit=1))
    assert web.max_active == 1, "limit=1 means one fetch at a time, saw %d at once" % web.max_active


def check8():
    takes(crawler.crawl_async, "max_pages", "timeout")
    budget = {u("/"): [u("/a"), u("/b"), u("/c")], u("/a"): [u("/d"), u("/e")], u("/b"): [u("/f")],
              u("/c"): [], u("/d"): [], u("/e"): [], u("/f"): []}
    for n, want in [(1, ["/"]), (4, ["/", "/a", "/b", "/c"]), (5, ["/", "/a", "/b", "/c", "/d"])]:
        web = FakeWeb(budget)
        got = run_async(crawler.crawl_async(u("/"), web.afetch, limit=2, max_pages=n))
        assert len(web.calls) <= n, "max_pages=%d but fetch was called %d times" % (n, len(web.calls))
        assert short(got) == want, "max_pages=%d should give the first %d pages in level order %r, got %r" % (n, n, want, short(got))
    web = FakeWeb({u("/"): [u("/slow"), u("/a")], u("/slow"): [u("/hidden")], u("/a"): [u("/b")], u("/b"): []}, slow=[u("/slow")])
    t = time.perf_counter()
    got = run_async(crawler.crawl_async(u("/"), web.afetch, timeout=0.05))
    took = time.perf_counter() - t
    assert took < 0.5, "/slow takes 3 s; timeout=0.05 should give up on it quickly, the crawl took %.2f s" % took
    assert web.cancelled == [u("/slow")], "the slow fetch should be cancelled when it times out, cancelled: %r" % short(web.cancelled)
    assert short(got) == ["/", "/a", "/b", "/slow"], "a timed-out page counts as tried (its links stay unknown), got %r" % short(got)


CHECKS = [check1, check2, check3, check4, check5, check6, check7, check8]


def run_up_to(n):
    for check in CHECKS[:n]:
        check()
