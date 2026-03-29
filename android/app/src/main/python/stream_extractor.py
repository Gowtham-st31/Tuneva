import yt_dlp

def extract_stream(url, title=None):
    if not url:
        return None

    try:
        ydl_opts = {
            "quiet": True,
            "format": "bestaudio/best",
            "nocheckcertificate": True,
            "noplaylist": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return None

        # handle playlist
        if "entries" in info:
            info = next((e for e in info["entries"] if e), None)

        if not info:
            return None

        stream_url = info.get("url")
        title = info.get("title")
        thumbnail = info.get("thumbnail")

        if not stream_url:
            return None

        return {
            "stream_url": stream_url,
            "title": title,
            "thumbnail": thumbnail,
        }

    except Exception as e:
        print("YT-DLP ERROR:", e)
        return None