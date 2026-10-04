from collections import deque


def crawl(start, fetch, max_depth=None):
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        url, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for link in fetch(url):
            if link not in seen:
                seen.add(link)
                queue.append((link, depth + 1))
    return seen
