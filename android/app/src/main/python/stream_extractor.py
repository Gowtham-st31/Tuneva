import concurrent.futures
import threading
import yt_dlp


def _pick_best_audio_format(info_dict):
    try:
        formats = info_dict.get("formats") or []
        if not formats:
            return None

        audio_formats = []
        for fmt in formats:
            if not isinstance(fmt, dict):
                continue
            acodec = fmt.get("acodec")
            if acodec and acodec != "none":
                audio_formats.append(fmt)

        if not audio_formats:
            return None

        def fmt_score(fmt):
            score = 0
            if fmt.get("ext") == "m4a":
                score += 10000
            abr = fmt.get("abr") or 0
            tbr = fmt.get("tbr") or 0
            score += int(abr) + int(tbr)
            return score

        audio_formats.sort(key=fmt_score, reverse=True)
        return audio_formats[0]
    except Exception:
        return None


_extraction_lock = threading.Lock()
_EXTRACTION_TIMEOUT = 10


def _normalize_info_entry(info):
    if not info or not isinstance(info, dict):
        return None

    entries = info.get("entries") or []
    if entries:
        for entry in entries:
            if not entry or not isinstance(entry, dict):
                continue
            if entry.get("url"):
                return entry
            fmt = _pick_best_audio_format(entry)
            if fmt and fmt.get("url"):
                return {
                    "url": fmt.get("url"),
                    "title": entry.get("title"),
                    "thumbnail": entry.get("thumbnail"),
                }
        return None

    if info.get("url"):
        return info

    fmt = _pick_best_audio_format(info)
    if fmt and fmt.get("url"):
        return {
            "url": fmt.get("url"),
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
        }

    return None


def _run_ydl_extract(ydl_opts, url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def extract_stream(url, title=None):
    if not url:
        return None

    if not _extraction_lock.acquire(blocking=False):
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            attempts = []

            attempts.append(
                {
                    "quiet": True,
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                    "nocheckcertificate": True,
                    "noplaylist": True,
                    "ignoreerrors": True,
                    "extractor_args": {"youtube": {"player_client": ["android"]}},
                }
            )

            attempts.append(
                {
                    "quiet": True,
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                    "cookiefile": "cookies.txt",
                    "nocheckcertificate": True,
                    "noplaylist": True,
                    "ignoreerrors": True,
                    "http_headers": {"User-Agent": "Mozilla/5.0"},
                }
            )

            attempts.append(
                {
                    "quiet": True,
                    "format": "bestaudio/best",
                    "nocheckcertificate": True,
                    "noplaylist": True,
                    "ignoreerrors": True,
                }
            )

            for ydl_opts in attempts:
                future = executor.submit(_run_ydl_extract, ydl_opts, url)
                try:
                    info = future.result(timeout=_EXTRACTION_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    info = None
                except Exception:
                    info = None

                entry = _normalize_info_entry(info)
                if entry and entry.get("url"):
                    return {
                        "stream_url": entry.get("url"),
                        "title": entry.get("title"),
                        "thumbnail": entry.get("thumbnail"),
                    }

            if title:
                try:
                    search_query = f"ytsearch3:{title}"
                    search_opts = {
                        "quiet": True,
                        "noplaylist": True,
                        "ignoreerrors": True,
                        "nocheckcertificate": True,
                        "extract_flat": "in_playlist",
                    }

                    future = executor.submit(_run_ydl_extract, search_opts, search_query)
                    try:
                        info = future.result(timeout=_EXTRACTION_TIMEOUT)
                    except concurrent.futures.TimeoutError:
                        future.cancel()
                        info = None
                    except Exception:
                        info = None

                    entries = (info or {}).get("entries") or []
                    for candidate in entries[:3]:
                        if not candidate or not isinstance(candidate, dict):
                            continue

                        cand_url = candidate.get("webpage_url") or (
                            "https://www.youtube.com/watch?v=" + (candidate.get("id") or "")
                        )
                        if not cand_url:
                            continue

                        for ydl_opts in attempts:
                            future = executor.submit(_run_ydl_extract, ydl_opts, cand_url)
                            try:
                                cinfo = future.result(timeout=_EXTRACTION_TIMEOUT)
                            except concurrent.futures.TimeoutError:
                                future.cancel()
                                cinfo = None
                            except Exception:
                                cinfo = None

                            centry = _normalize_info_entry(cinfo)
                            if centry and centry.get("url"):
                                return {
                                    "stream_url": centry.get("url"),
                                    "title": centry.get("title") or title,
                                    "thumbnail": centry.get("thumbnail"),
                                }
                except Exception:
                    pass
    finally:
        try:
            _extraction_lock.release()
        except Exception:
            pass

    return None
