"""
Local server entrypoint for building a standalone executable.
"""

import sys
import os
import socket

# 🔥 FORCE CORRECT PATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 🔥 NOW IMPORT CORRECT app.py
from app import app


def _find_free_port(default_port=5001):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", default_port))
        s.close()
        return default_port
    except Exception:
        return 0


if __name__ == "__main__":
    port = int(os.environ.get("TUNEVA_PORT", "5001"))
    free = _find_free_port(port)

    if free == 0:
        port = 5001
    else:
        port = free

    print("🚀 STARTING LOCAL SERVER...")
    app.run(host="127.0.0.1", port=port, debug=False)