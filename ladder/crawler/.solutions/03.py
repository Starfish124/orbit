from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse


def normalize(page, link):
    return urldefrag(urljoin(page, link)).url


def crawl(start, fetch, max_depth=None):
    host = urlparse(start).netloc
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        url, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for link in fetch(url):
            link = normalize(url, link)
            if urlparse(link).netloc != host:
                continue
            if link not in seen:
                seen.add(link)
                queue.append((link, depth + 1))
    return seen
