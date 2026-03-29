import yt_dlp
from urllib.parse import parse_qs, urlparse


def _extract_video_id(youtube_url):
    if not youtube_url:
        return None

    parsed = urlparse(youtube_url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        return parsed.path.strip("/") or None

    if "youtube.com" in host:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]

        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            parts = [p for p in parsed.path.split("/") if p]
            return parts[1] if len(parts) > 1 else None

    return None


def _fallback_thumbnail(youtube_url):
    video_id = _extract_video_id(youtube_url)
    if not video_id:
        return None
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

def extract_playlist(url):

    ydl_opts = {
    "quiet": True,
    "extract_flat": "in_playlist",
    "ignoreerrors": True,
    "cookiefile": "cookies.txt"
}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    videos = []

    for entry in info.get("entries", []):

        if not entry:
            continue

        youtube_url = entry.get("webpage_url") or entry.get("url")
        if youtube_url and str(youtube_url).startswith("/"):
            youtube_url = f"https://www.youtube.com{youtube_url}"
        thumbnail = entry.get("thumbnail")

        if not thumbnail:
            thumbs = entry.get("thumbnails") or []
            if thumbs:
                thumbnail = thumbs[-1].get("url") or thumbs[0].get("url")

        if not thumbnail:
            thumbnail = _fallback_thumbnail(youtube_url)

        videos.append({
            "title": entry.get("title"),
            "youtube_url": youtube_url,
            "thumbnail": thumbnail
        })

    return videos