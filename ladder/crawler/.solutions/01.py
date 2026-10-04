from collections import deque


def crawl(start, fetch):
    seen = {start}
    queue = deque([start])
    while queue:
        url = queue.popleft()
        for link in fetch(url):
            if link not in seen:
                seen.add(link)
                queue.append(link)
    return seen
