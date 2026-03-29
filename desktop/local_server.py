import os
import sys


# Ensure repository root is importable when this script is run from desktop/
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app  # noqa: E402


if __name__ == "__main__":
    # Fixed localhost:5001 as requested for local engine
    app.run(host="127.0.0.1", port=5001, debug=False)
