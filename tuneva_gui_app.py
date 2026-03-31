import sys
import os
import json
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
from cachetools import TTLCache
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Create folders
os.makedirs("cache", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Persistent cache file
CACHE_FILE = "stream_cache.json"

# Memory cache
stream_cache = TTLCache(maxsize=1000, ttl=86400)

# Load saved cache on startup
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            saved_cache = json.load(f)
            stream_cache.update(saved_cache)
    except Exception as e:
        print("CACHE LOAD ERROR:", e)

app = Flask(__name__)
CORS(app)


def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(dict(stream_cache), f)
    except Exception as e:
        print("CACHE SAVE ERROR:", e)


def extract_stream(url):
    if not url:
        return {
            "stream_url": "",
            "title": "",
            "thumbnail": ""
        }

    # Use cached stream if available
    if url in stream_cache:
        return stream_cache[url]

    ydl_opts = {
        "quiet": True,
        "format": "bestaudio",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "cachedir": "cache"
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            return {
                "stream_url": "",
                "title": "",
                "thumbnail": ""
            }

        # Playlist/search support
        if "entries" in info:
            info = next((e for e in info["entries"] if e), None)

        if not info:
            return {
                "stream_url": "",
                "title": "",
                "thumbnail": ""
            }

        result = {
            "stream_url": info.get("url", ""),
            "title": info.get("title", ""),
            "thumbnail": info.get("thumbnail", "")
        }

        # Save in memory + file cache
        stream_cache[url] = result
        save_cache()

        return result

    except Exception as e:
        print("STREAM ERROR:", e)
        return {
            "stream_url": "",
            "title": "",
            "thumbnail": ""
        }


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

    return jsonify(extract_stream(url))


def run_server():
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=False,
        use_reloader=False,
        threaded=True
    )


class TunevaWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Tuneva")
        self.setFixedSize(400, 250)

        layout = QVBoxLayout()

        logo = QLabel("🎵")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFont(QFont("Arial", 40))

        text = QLabel("Tuneva is Running")
        text.setAlignment(Qt.AlignCenter)
        text.setFont(QFont("Arial", 18))

        info = QLabel("Keep this window open while playing songs")
        info.setAlignment(Qt.AlignCenter)
        info.setFont(QFont("Arial", 10))

        layout.addWidget(logo)
        layout.addWidget(text)
        layout.addWidget(info)

        self.setLayout(layout)


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()

    qt_app = QApplication(sys.argv)
    window = TunevaWindow()
    window.show()
    sys.exit(qt_app.exec_())