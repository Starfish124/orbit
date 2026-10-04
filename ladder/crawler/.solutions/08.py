import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urldefrag, urljoin, urlparse


def normalize(page, link):
    return urldefrag(urljoin(page, link)).url


def clean_links(page, links, host):
    out = []
    for link in links:
        link = normalize(page, link)
        if urlparse(link).netloc == host:
            out.append(link)
    return out


def fetch_with_retries(fetch, url, retries):
    for attempt in range(retries + 1):
        try:
            return fetch(url)
        except Exception as e:
            last_error = e
    raise last_error


def crawl(start, fetch, max_depth=None, errors=None, retries=0):
    host = urlparse(start).netloc
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        url, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        try:
            links = fetch_with_retries(fetch, url, retries)
        except Exception as e:
            if errors is not None:
                errors[url] = e
            continue
        for link in clean_links(url, links, host):
            if link not in seen:
                seen.add(link)
                queue.append((link, depth + 1))
    return seen


def crawl_threaded(start, fetch, workers=8):
    host = urlparse(start).netloc

    def safe_fetch(url):
        try:
            return fetch(url)
        except Exception:
            return []

    # only this (main) thread touches `seen`; the workers just fetch
    seen = {start}
    level = [start]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while level:
            next_level = []
            for url, links in zip(level, pool.map(safe_fetch, level)):
                for link in clean_links(url, links, host):
                    if link not in seen:
                        seen.add(link)
                        next_level.append(link)
            level = next_level
    return seen


async def crawl_async(start, fetch, limit=None, max_pages=None, timeout=None):
    host = urlparse(start).netloc
    gate = None
    if limit is not None:
        gate = asyncio.Semaphore(limit)

    async def safe_fetch(url):
        try:
            if gate is None:
                return await asyncio.wait_for(fetch(url), timeout)
            async with gate:
                return await asyncio.wait_for(fetch(url), timeout)
        except Exception:
            return []

    seen = {start}
    fetched = set()
    level = [start]
    while level:
        if max_pages is not None:
            level = level[:max_pages - len(fetched)]
        fetched.update(level)
        results = await asyncio.gather(*[safe_fetch(url) for url in level])
        next_level = []
        for url, links in zip(level, results):
            for link in clean_links(url, links, host):
                if link not in seen:
                    seen.add(link)
                    next_level.append(link)
        level = next_level
    return fetched
