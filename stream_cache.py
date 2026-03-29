from cachetools import TTLCache
from stream_extractor import extract_stream
import time

# cache for 6 hours (reduce repeated yt-dlp calls)
stream_cache = TTLCache(maxsize=500, ttl=60 * 60 * 6)

# How many *additional* retries to attempt when extraction fails
# Total attempts = 1 + MAX_RETRIES
MAX_RETRIES = 2


def get_stream(url, title=None):
    if not url:
        return None

    # 1️⃣ check cache
    try:
        if url in stream_cache:
            return stream_cache[url]
    except Exception:
        pass

    # 2️⃣ fetch from extractor with retries (which itself uses multiple fallbacks)
    result = None
    for attempt in range(0, MAX_RETRIES + 1):
        try:
            result = extract_stream(url, title=title)
        except Exception:
            result = None

        if result:
            # 3️⃣ store cache and return
            try:
                stream_cache[url] = result
            except Exception:
                pass
            return result

        # small backoff before retrying
        if attempt < MAX_RETRIES:
            try:
                time.sleep(0.5 + attempt * 0.2)
            except Exception:
                pass

    return None