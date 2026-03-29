import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _load_env_file():
	env_path = os.path.join(os.path.dirname(__file__), ".env")
	if not os.path.exists(env_path):
		return

	with open(env_path, "r", encoding="utf-8") as env_file:
		for raw_line in env_file:
			line = raw_line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue

			key, value = line.split("=", 1)
			key = key.strip()
			value = value.strip().strip('"').strip("'")

			if not key:
				continue

			# Ensure .env Mongo settings are always used, even if stale shell env values exist.
			if key.startswith("MONGODB_"):
				os.environ[key] = value
			elif key not in os.environ:
				os.environ[key] = value


def _ensure_uri_query_param(uri, param_key, param_value):
	parts = urlsplit(uri)
	query = dict(parse_qsl(parts.query, keep_blank_values=True))
	if param_key not in query and param_value:
		query[param_key] = param_value
	new_query = urlencode(query)
	return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


_load_env_file()

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise Exception("MONGODB_URI not set in environment")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "yt_music")
MONGODB_AUTH_SOURCE = os.getenv("MONGODB_AUTH_SOURCE", "admin")

if MONGODB_URI.startswith("mongodb+srv://"):
	MONGODB_URI = _ensure_uri_query_param(MONGODB_URI, "authSource", MONGODB_AUTH_SOURCE)
	client = MongoClient(MONGODB_URI, server_api=ServerApi("1"))
else:
	client = MongoClient(MONGODB_URI)

db = client[MONGODB_DB_NAME]

users = db["users"]
playlists = db["playlists"]
otp_requests = db["otp_requests"]
user_playlists = db["user_playlists"]