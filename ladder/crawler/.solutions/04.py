from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse


def normalize(page, link):
    return urldefrag(urljoin(page, link)).url


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
        for link in links:
            link = normalize(url, link)
            if urlparse(link).netloc != host:
                continue
            if link not in seen:
                seen.add(link)
                queue.append((link, depth + 1))
    return seen
