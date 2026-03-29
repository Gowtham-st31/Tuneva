import time
from cachetools import TTLCache
from stream_extractor import extract_stream

stream_cache = TTLCache(maxsize=500, ttl=60 * 60 * 6)
MAX_RETRIES = 2


def get_stream(url, title=None):
    if not url:
        return None

    try:
        if url in stream_cache:
            return stream_cache[url]
    except Exception:
        pass

    result = None
    for attempt in range(0, MAX_RETRIES + 1):
        try:
            result = extract_stream(url, title=title)
        except Exception:
            result = None

        if result:
            try:
                stream_cache[url] = result
            except Exception:
                pass
            return result

        if attempt < MAX_RETRIES:
            try:
                time.sleep(0.5 + attempt * 0.2)
            except Exception:
                pass

    return None
