import threading
import tkinter as tk
from tkinter import ttk
from flask import Flask, jsonify, request
from flask_cors import CORS
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

    result = {
        "stream_url": info.get("url", ""),
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


def run_server():
    app.run(host="127.0.0.1", port=5001)


def start_gui():
    root = tk.Tk()
    root.title("Tuneva")
    root.geometry("400x250")
    root.resizable(False, False)

    # Logo text
    title = tk.Label(
        root,
        text="🎵 TUNEVA",
        font=("Arial", 24, "bold")
    )
    title.pack(pady=30)

    status = tk.Label(
        root,
        text="Tuneva Local Engine Running ✅",
        font=("Arial", 14)
    )
    status.pack(pady=20)

    info = tk.Label(
        root,
        text="Keep this window open while playing songs",
        font=("Arial", 10)
    )
    info.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    start_gui()