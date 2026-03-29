"""Local Flask server for Tuneva Android WebView playback."""

import threading
import traceback
from flask import Flask, jsonify, request
from flask_cors import CORS

# 🔥 SAFE IMPORT
try:
    from stream_cache import get_stream
except Exception as e:
    print("IMPORT ERROR (stream_cache):", e)
    get_stream = None

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

_server_thread = None
_server_lock = threading.Lock()


def _empty_payload():
    return {
        "stream_url": "",
        "title": "",
        "thumbnail": "",
    }


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "tuneva-local-engine"}), 200


@app.route("/local-stream")
def local_stream():
    url = request.args.get("url", "").strip()
    title = request.args.get("title", "").strip()

    if not url or url == "test":
        return jsonify(_empty_payload()), 200

    try:
        # 🔥 SAFE CHECK
        if get_stream is None:
            print("get_stream not available")
            return jsonify(_empty_payload()), 200

        data = get_stream(url, title=title)

        if not data or not data.get("stream_url"):
            return jsonify(_empty_payload()), 200

        return jsonify({
            "stream_url": data.get("stream_url", ""),
            "title": data.get("title", ""),
            "thumbnail": data.get("thumbnail", ""),
        }), 200

    except Exception as error:
        print("LOCAL STREAM ERROR:", error)
        traceback.print_exc()
        return jsonify(_empty_payload()), 200


def _run_server(host, port):
    try:
        print(f"🚀 Starting Flask on {host}:{port}")
        app.run(
            host=host,
            port=int(port),
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print("SERVER START ERROR:", e)
        traceback.print_exc()


def start_server(host="127.0.0.1", port=5001):
    global _server_thread

    with _server_lock:
        if _server_thread and _server_thread.is_alive():
            return True

        _server_thread = threading.Thread(
            target=_run_server,
            args=(host, int(port)),
            daemon=True,
            name="tuneva-local-flask",
        )

        try:
            _server_thread.start()
            print("✅ Server thread started")
        except Exception as e:
            print("THREAD START ERROR:", e)
            traceback.print_exc()

    return True


if __name__ == "__main__":
    _run_server("127.0.0.1", 5001)