import json
import re
import yt_dlp


NOISE_WORDS = [
    "official",
    "video",
    "song",
    "hd",
    "lyrics",
    "full",
    "4k",
    "status",
    "music",
    "audio",
]


def _clean_title_for_search(title):
    if not title:
        return ""
    s = str(title).lower()
    for word in NOISE_WORDS:
        s = s.replace(word, " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize(info):
    if not isinstance(info, dict):
        return None

    entries = info.get("entries") or []
    if entries:
        for e in entries:
            if not isinstance(e, dict):
                continue
            if e.get("url"):
                return {
                    "stream_url": e.get("url"),
                    "title": e.get("title") or "",
                    "thumbnail": e.get("thumbnail") or "",
                    "duration": e.get("duration")
                }
        return None

    if info.get("url"):
        return {
            "stream_url": info.get("url"),
            "title": info.get("title") or "",
            "thumbnail": info.get("thumbnail") or "",
            "duration": info.get("duration")
        }

    fmts = info.get("formats") or []
    for f in fmts:
        if not isinstance(f, dict):
            continue
        if f.get("acodec") and f.get("acodec") != "none" and f.get("url"):
            return {
                "stream_url": f.get("url"),
                "title": info.get("title") or "",
                "thumbnail": info.get("thumbnail") or "",
                "duration": info.get("duration")
            }

    return None


def _opts(player_client=None, fmt="bestaudio/best"):
    y_extractor_args = {
        "player_skip": ["js"]
    }
    if player_client:
        y_extractor_args["player_client"] = [player_client]

    return {
        "quiet": True,
        "noplaylist": True,
        "ignoreerrors": True,
        "format": fmt,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": y_extractor_args
        },
    }


def _extract_once(target, player_client=None, fmt="bestaudio/best"):
    try:
        with yt_dlp.YoutubeDL(_opts(player_client=player_client, fmt=fmt)) as ydl:
            info = ydl.extract_info(target, download=False)
            return _normalize(info), None
    except Exception as exc:
        return None, str(exc)


def _is_region_block(err):
    if not err:
        return False
    s = err.lower()
    return "not available in your country" in s


def _looks_url(value):
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _search_alternative(seed_text):
    clean = _clean_title_for_search(seed_text)
    query_text = clean or str(seed_text or "").strip()
    if not query_text:
        return None

    search_q = f"ytsearch2:{query_text} audio"

    search_opts = {
        "quiet": True,
        "ignoreerrors": True,
        "noplaylist": True,
        "extract_flat": "in_playlist",
        "extractor_args": {
            "youtube": {
                "player_skip": ["js"]
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            info = ydl.extract_info(search_q, download=False)
    except Exception:
        return None

    entries = (info or {}).get("entries") or []
    for c in entries:
        if not isinstance(c, dict):
            continue
        c_url = c.get("webpage_url")
        if not c_url and c.get("id"):
            c_url = f"https://www.youtube.com/watch?v={c.get('id')}"
        if not c_url:
            continue
        if "shorts" in c_url.lower():
            continue
        duration = c.get("duration")
        if isinstance(duration, (int, float)) and duration < 30:
            continue

        # Fallback order over client and formats
        for client in ["android", "web", None]:
            for fmt in ["bestaudio/best", "best", "worstaudio/worst"]:
                res, _ = _extract_once(c_url, player_client=client, fmt=fmt)
                if not res:
                    continue
                if isinstance(res.get("duration"), (int, float)) and res.get("duration") < 30:
                    continue
                return {
                    "stream_url": res.get("stream_url", ""),
                    "title": res.get("title") or c.get("title") or "",
                    "thumbnail": res.get("thumbnail") or c.get("thumbnail") or ""
                }

    return None


def extract_stream(url_or_title):
    target = str(url_or_title or "").strip()
    if not target:
        return json.dumps({"error": "unavailable", "stream_url": "", "title": "", "thumbnail": ""})

    region_blocked = False

    # A) Android client -> B) Web client -> C) Generic
    for client in ["android", "web", None]:
        for fmt in ["bestaudio/best", "best", "worstaudio/worst"]:
            result, err = _extract_once(target, player_client=client, fmt=fmt)
            if result and result.get("stream_url"):
                return json.dumps({
                    "stream_url": result.get("stream_url", ""),
                    "title": result.get("title", ""),
                    "thumbnail": result.get("thumbnail", "")
                })
            if _is_region_block(err):
                region_blocked = True
                break
        if region_blocked:
            break

    # If region-blocked or normal extraction fails, search an alternative
    seed = target if not _looks_url(target) else ""
    alt = _search_alternative(seed)
    if alt and alt.get("stream_url"):
        return json.dumps(alt)

    return json.dumps({"error": "unavailable", "stream_url": "", "title": "", "thumbnail": ""})
