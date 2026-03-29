import yt_dlp
import threading
import concurrent.futures
import time


def _pick_best_audio_format(info_dict):
    # Given an info dict with 'formats', pick the best audio format and return it
    try:
        formats = info_dict.get("formats") or []
        if not formats:
            return None

        # Filter for audio-capable formats
        audio_formats = []
        for f in formats:
            if not isinstance(f, dict):
                continue
            # acodec != 'none' indicates audio present
            acodec = f.get("acodec")
            if acodec and acodec != "none":
                audio_formats.append(f)

        if not audio_formats:
            return None

        # Prefer formats with ext m4a, then highest abr or tbr
        def fmt_score(f):
            score = 0
            if f.get("ext") == "m4a":
                score += 10000
            # approximate bitrate
            abr = f.get("abr") or 0
            tbr = f.get("tbr") or 0
            score += int(abr) + int(tbr)
            return score

        audio_formats.sort(key=fmt_score, reverse=True)
        return audio_formats[0]
    except Exception:
        return None

# Global lock to avoid concurrent yt-dlp extractions in the same process
_extraction_lock = threading.Lock()
_EXTRACTION_TIMEOUT = 10  # seconds


def _normalize_info_entry(info):
    # Normalize info returned by yt-dlp. Prefer an entry with a usable 'url'.
    if not info or not isinstance(info, dict):
        return None

    # If a playlist-like result, iterate entries for first usable one
    entries = info.get("entries") or []
    if entries:
        for entry in entries:
            if not entry or not isinstance(entry, dict):
                continue
            if entry.get("url"):
                return entry
            # try to derive a playable url from formats list
            fm = _pick_best_audio_format(entry)
            if fm and fm.get("url"):
                return {"url": fm.get("url"), "title": entry.get("title"), "thumbnail": entry.get("thumbnail")}
        return None

    # Single video result
    if info.get("url"):
        return info

    fm = _pick_best_audio_format(info)
    if fm and fm.get("url"):
        return {"url": fm.get("url"), "title": info.get("title"), "thumbnail": info.get("thumbnail")}

    return None


def _run_ydl_extract(ydl_opts, url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def extract_stream(url, title=None):
    # Prevent multiple simultaneous extractions in this process
    if not url:
        return None

    if not _extraction_lock.acquire(blocking=False):
        # Another extraction is in progress; avoid overload
        return None

    try:
        # Use a thread to allow a timeout around blocking extraction
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # Prepare a list of sequential extraction attempts (multi-fallback)
            attempts = []

            # 1) Android client (often returns m4a streams)
            attempts.append({
                "quiet": True,
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "nocheckcertificate": True,
                "noplaylist": True,
                "ignoreerrors": True,
                "extractor_args": {"youtube": {"player_client": ["android"]}}
            })

            # 2) Web client with cookies (may help for signed or age-restricted content)
            attempts.append({
                "quiet": True,
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "cookiefile": "cookies.txt",
                "nocheckcertificate": True,
                "noplaylist": True,
                "ignoreerrors": True,
                "http_headers": {"User-Agent": "Mozilla/5.0"}
            })

            # 3) Generic best audio fallback (no cookies, no special client)
            attempts.append({
                "quiet": True,
                "format": "bestaudio/best",
                "nocheckcertificate": True,
                "noplaylist": True,
                "ignoreerrors": True
            })

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
                        "thumbnail": entry.get("thumbnail")
                    }

            # If original extraction failed and a title is provided, try searching
            if title:
                try:
                    search_query = f"ytsearch3:{title}"
                    search_opts = {
                        "quiet": True,
                        "noplaylist": True,
                        "ignoreerrors": True,
                        "nocheckcertificate": True,
                        "extract_flat": "in_playlist"
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
                    # Try top 3 search results
                    for candidate in entries[:3]:
                        if not candidate or not isinstance(candidate, dict):
                            continue

                        cand_url = candidate.get("webpage_url") or ("https://www.youtube.com/watch?v=" + (candidate.get("id") or ""))
                        if not cand_url:
                            continue

                        # Try same extraction attempts for the candidate url
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
                                    "thumbnail": centry.get("thumbnail")
                                }
                except Exception:
                    # Swallow errors - do not surface to caller
                    pass
    finally:
        try:
            _extraction_lock.release()
        except Exception:
            pass

    return None