from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import yt_dlp
from cachetools import TTLCache

app = Flask(__name__)
CORS(app)

stream_cache = TTLCache(maxsize=300, ttl=3600)


def extract_stream(url):
    if url in stream_cache:
        return stream_cache[url]

    ydl_opts = {
        "quiet": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    stream_url = info.get("url")

    result = {
        "stream_url": stream_url,
        "title": info.get("title", ""),
        "thumbnail": info.get("thumbnail", "")
    }

    stream_cache[url] = result
    return result


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/local-stream")
def local_stream():
    url = request.args.get("url", "").strip()

    if not url or url == "test":
        return jsonify({
            "stream_url": "",
            "title": "",
            "thumbnail": ""
        })

    try:
        return jsonify(extract_stream(url))
    except Exception as e:
        print("STREAM ERROR:", e)
        return jsonify({
            "stream_url": "",
            "title": "",
            "thumbnail": ""
        })


if __name__ == "__main__":
    print("Tuneva Local Engine Running on 127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001)