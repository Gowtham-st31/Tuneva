print("🔥 crt APP.PY LOADED")
from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory, abort
from flask_cors import CORS
from db import users, playlists, otp_requests, user_playlists
from extractor import extract_playlist
import yt_dlp
import random
import os
from stream_cache import get_stream
import requests
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from bson import ObjectId


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

            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file()

app = Flask(__name__)
@app.route("/local-stream")
def local_stream():
    print("🔥 LOCAL STREAM HIT")

    url = request.args.get("url")

    # ✅ ENGINE CHECK (IMPORTANT)
    if not url or url == "test":
        return jsonify({
            "stream_url": "",
            "title": "",
            "thumbnail": ""
        }), 200

    try:
        # 🔥 YOUR ACTUAL EXTRACTION LOGIC HERE
        data = get_stream(url)  # or whatever function you use

        # ✅ SAFETY CHECK
        if not data or not data.get("stream_url"):
            return jsonify({
                "stream_url": "",
                "title": "",
                "thumbnail": ""
            }), 200

        return jsonify(data)

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({
            "stream_url": "",
            "title": "",
            "thumbnail": ""
        }), 200
@app.route("/test123")
def test123():
    return "WORKING"
app.secret_key = "secret"

# Enable CORS for API endpoints so mobile apps and external clients can call
# the streaming API. Allow all origins for now to support diverse clients.
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route('/download/<path:filename>')
def download_file(filename):
    """Serve files from static/downloads with Content-Disposition attachment.

    This forces the browser to prompt a download and prevents direct inline rendering.
    """
    downloads_dir = os.path.join(os.path.dirname(__file__), "static", "downloads")

    # Prevent path traversal
    requested_path = os.path.normpath(os.path.join(downloads_dir, filename))
    if not requested_path.startswith(os.path.normpath(downloads_dir)):
        abort(403)

    if not os.path.exists(requested_path):
        abort(404)

    return send_from_directory(downloads_dir, filename, as_attachment=True)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")

AVAILABLE_LANGUAGES = [
    "tamil",
    "hindi",
    "english",
    "telugu",
    "malayalam",
    "kannada",
    "punjabi",
    "marathi",
    "bengali",
    "gujarati"
]

ADMIN_EMAILS = {
    email.strip().lower()
    for email in (os.getenv("ADMIN_EMAILS") or "tuneva2026@gmail.com,tuvena2026@gmail.com").split(",")
    if email.strip()
}

LIVE_PLAYLIST_CACHE_TTL_SECONDS = 180
_live_playlist_cache = {}


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


def _thumbnail_from_video_url(youtube_url):
    video_id = _extract_video_id(youtube_url)
    if not video_id:
        return None
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _resolve_thumbnail(video):
    thumb = video.get("thumbnail")
    if thumb:
        return thumb
    return _thumbnail_from_video_url(video.get("youtube_url"))


def _video_key(youtube_url):
    """Return a canonical key for a youtube URL.

    Prefer the extracted video id when possible, otherwise return a
    normalized URL string. This is used to compare and store blocked
    entries in a resilient way across different YouTube URL formats.
    """
    if not youtube_url:
        return None
    vid = _extract_video_id(youtube_url)
    if vid:
        return vid
    return str(youtube_url).strip().lower()


def _key_of(youtube_url):
    """Safe canonical key for a youtube URL (fallback without relying on other helpers)."""
    if not youtube_url:
        return None
    vid = _extract_video_id(youtube_url)
    if vid:
        return vid
    return str(youtube_url).strip().lower()


def _get_user_languages(user):
    language_value = user.get("language")

    if isinstance(language_value, list):
        return [lang for lang in language_value if isinstance(lang, str) and lang.strip()]

    if isinstance(language_value, str) and language_value.strip():
        return [language_value]

    return []


def _get_current_user():
    email = session.get("user_email")
    if not email:
        return None
    return users.find_one({"email": email})


def _is_admin_email(email):
    return isinstance(email, str) and email.strip().lower() in ADMIN_EMAILS


def _is_admin_user(user):
    if not user:
        return False
    return bool(user.get("is_admin")) or _is_admin_email(user.get("email", ""))


def _serialize_user_playlist(doc):
    return {
        "id": str(doc.get("_id")),
        "name": doc.get("name", "Untitled"),
        "description": doc.get("description", ""),
        "songs": doc.get("songs", []),
        "created_at": doc.get("created_at")
    }


def _safe_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        return None


def _safe_playlist_field_key(value):
    return str(value or "").replace(".", "_").replace("$", "_").strip()


def _is_valid_gmail(email):
    return isinstance(email, str) and email.endswith("@gmail.com") and "@" in email


def _require_login_redirect():
    if not session.get("user_email"):
        return redirect("/")
    return None


def _extract_playlist_live_cached(source_url, fallback_videos=None):
    now = datetime.utcnow()
    cached = _live_playlist_cache.get(source_url)
    if cached:
        expires_at, payload = cached
        if expires_at > now:
            return payload

    try:
        videos = extract_playlist(source_url)
        _live_playlist_cache[source_url] = (
            now + timedelta(seconds=LIVE_PLAYLIST_CACHE_TTL_SECONDS),
            videos
        )
        return videos
    except Exception:
        return fallback_videos or []


def _get_videos_for_languages(languages):
    if not languages:
        return []

    cursor = playlists.find({"language": {"$in": languages}})

    all_videos = []
    seen_urls = set()

    for playlist_doc in cursor:
        playlist_name = (
            playlist_doc.get("playlist_name")
            or playlist_doc.get("language")
            or "Playlist"
        )

        # Merge live/fallback videos and preserve stored blocked flags (or blocked_urls)
        stored_videos = playlist_doc.get("videos", []) or []
        # Map canonical video key -> blocked flag for stored videos
        stored_blocked_map = {
            _video_key(v.get("youtube_url")): bool(v.get("blocked"))
            for v in stored_videos
            if v.get("youtube_url")
        }
        blocked_urls = set(
            k for k in (_video_key(u) for u in (playlist_doc.get("blocked_urls") or []))
            if k
        )

        playlist_videos = []
        source_url = str(playlist_doc.get("source_url", "")).strip()
        if source_url:
            playlist_videos = _extract_playlist_live_cached(
                source_url,
                fallback_videos=stored_videos
            )
        else:
            playlist_videos = stored_videos

        for video in playlist_videos:
            if not video:
                continue

            v = dict(video)
            v["thumbnail"] = _resolve_thumbnail(v)
            if not v.get("playlist_title"):
                v["playlist_title"] = playlist_name

            video_url = v.get("youtube_url")
            video_key = _video_key(video_url) or video_url

            # Determine blocked state: stored flag or playlist-level blocked list
            is_blocked = False
            if video_key:
                is_blocked = bool(stored_blocked_map.get(video_key) or (video_key in blocked_urls) or bool(v.get("blocked", False)))
                v["blocked"] = is_blocked

            # dedupe by canonical key so different URL formats don't duplicate
            if video_key in seen_urls:
                continue

            if video_key:
                seen_urls.add(video_key)

            all_videos.append(v)

    return all_videos


def _build_language_priority(selected_languages, language_play_counts):
    selected_set = set(selected_languages)
    play_counts = language_play_counts or {}

    selected_sorted = sorted(
        selected_languages,
        key=lambda lang: (-int(play_counts.get(lang, 0)), selected_languages.index(lang))
    )

    selected_rank = {lang: idx for idx, lang in enumerate(selected_sorted)}

    other_languages = [
        lang for lang in playlists.distinct("language")
        if isinstance(lang, str) and lang and lang not in selected_set
    ]
    other_sorted = sorted(
        other_languages,
        key=lambda lang: (-int(play_counts.get(lang, 0)), lang)
    )
    other_rank = {lang: idx for idx, lang in enumerate(other_sorted)}

    return selected_set, selected_rank, other_rank


def _get_prioritized_all_videos(user):
    selected_languages = _get_user_languages(user or {})
    language_play_counts = (user or {}).get("language_play_counts") or {}
    selected_set, selected_rank, other_rank = _build_language_priority(selected_languages, language_play_counts)

    all_videos = []
    seen_urls = set()
    is_admin = _is_admin_user(user or {})

    for playlist_doc in playlists.find({}):
        language = str(playlist_doc.get("language", "")).strip().lower()
        playlist_name = (
            playlist_doc.get("playlist_name")
            or playlist_doc.get("language")
            or "Playlist"
        )

        # Merge stored blocked flags and playlist-level blocked_urls
        stored_videos = playlist_doc.get("videos", []) or []
        stored_blocked_map = {
            _video_key(v.get("youtube_url")): bool(v.get("blocked"))
            for v in stored_videos
            if v.get("youtube_url")
        }
        blocked_urls = set(
            k for k in (_video_key(u) for u in (playlist_doc.get("blocked_urls") or []))
            if k
        )

        playlist_videos = []
        source_url = str(playlist_doc.get("source_url", "")).strip()
        if source_url:
            playlist_videos = _extract_playlist_live_cached(
                source_url,
                fallback_videos=stored_videos
            )
        else:
            playlist_videos = stored_videos

        for video in playlist_videos:
            if not video:
                continue

            v = dict(video)
            v["thumbnail"] = _resolve_thumbnail(v)
            v["language"] = language
            if not v.get("playlist_title"):
                v["playlist_title"] = playlist_name

            video_url = v.get("youtube_url")
            video_key = _video_key(video_url) or video_url

            # Determine blocked state
            is_blocked = False
            if video_key:
                is_blocked = bool(stored_blocked_map.get(video_key) or (video_key in blocked_urls) or bool(v.get("blocked", False)))
                v["blocked"] = is_blocked

            # Skip blocked videos for non-admin users
            if is_blocked and not is_admin:
                continue

            # Dedupe by canonical key
            if video_key in seen_urls:
                continue

            if video_key:
                seen_urls.add(video_key)

            all_videos.append(v)

    def _sort_key(video):
        lang = video.get("language", "")
        if lang in selected_set:
            return (0, selected_rank.get(lang, 10**6), video.get("playlist_title", ""), video.get("title", ""))
        return (1, other_rank.get(lang, 10**6), video.get("playlist_title", ""), video.get("title", ""))

    all_videos.sort(key=_sort_key)
    return all_videos


def _generate_otp_code():
    return f"{random.randint(0, 999999):06d}"


def _send_otp_email(recipient_email, otp_code, purpose):
    sender_email = (
        os.getenv("BREVO_SENDER_EMAIL")
        or os.getenv("BERO_SENDER_EMAIL")
        or os.getenv("SMTP_EMAIL")
    )
    sender_name = os.getenv("BREVO_SENDER_NAME") or os.getenv("BERO_SENDER_NAME", "MusicHub")

    if not sender_email:
        return False, "Email sender is not configured. Set BREVO_SENDER_EMAIL."

    if not BREVO_API_KEY:
        return False, "Brevo API key is missing. Set BREVO_API_KEY."

    subject = "MusicHub OTP Verification"
    if purpose == "reset":
        subject = "MusicHub Password Reset OTP"

    body = (
        "Hello,<br><br>"
        f"Your OTP for MusicHub is: <b>{otp_code}</b><br>"
        "It is valid for 10 minutes.<br><br>"
        "If you did not request this, you can ignore this email.<br><br>"
        f"- {sender_name}"
    )

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [{"email": recipient_email}],
        "subject": subject,
        "htmlContent": body
    }

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers=headers,
            json=payload,
            timeout=20
        )
        if response.status_code >= 400:
            return False, "Unable to send OTP email. Check Brevo API key and sender settings."
    except Exception:
        return False, "Unable to send OTP email. Check your internet connection and Brevo settings."

    return True, "OTP sent successfully."


def _create_otp_request(email, purpose, payload):
    otp_code = _generate_otp_code()
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    otp_requests.delete_many({"email": email, "purpose": purpose})
    otp_requests.insert_one({
        "email": email,
        "purpose": purpose,
        "otp": otp_code,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
        "payload": payload
    })

    return otp_code


def _find_valid_otp_request(email, purpose, otp_code):
    return otp_requests.find_one({
        "email": email,
        "purpose": purpose,
        "otp": otp_code,
        "expires_at": {"$gt": datetime.utcnow()}
    })


# HOME
@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user_email"):
        user = _get_current_user()
        if user and not _get_user_languages(user):
            return redirect("/language")
        # If already an admin, redirect to admin dashboard
        if _is_admin_user(user):
            return redirect("/admin")
        return redirect("/playlist")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="Email and password are required.")

        user = users.find_one({
            "email": email,
            "password": password,
            "email_verified": True
        })

        if not user:
            return render_template("login.html", error="Invalid Gmail or password.")

        if user.get("is_blocked"):
            return render_template("login.html", error="Your account is blocked. Contact admin.")

        # Keep persisted admin status aligned for configured admin emails.
        if _is_admin_email(email) and not user.get("is_admin"):
            users.update_one({"email": email}, {"$set": {"is_admin": True}})

        session["user_email"] = email
        if not _get_user_languages(user):
            return redirect("/language")
        # If this account is an admin email, send to admin dashboard
        if _is_admin_email(email) or _is_admin_user(user):
            return redirect("/admin")
        return redirect("/playlist")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_email", None)
    return redirect("/")


# REGISTER
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("register.html", error="Email and password are required.")

        if not _is_valid_gmail(email):
            return render_template("register.html", error="Please enter a valid Gmail address.")

        if users.find_one({"email": email}):
            return render_template("register.html", error="Email is already registered.")

        otp_code = _create_otp_request(email, "register", {
            "email": email,
            "password": password
        })

        sent, message = _send_otp_email(email, otp_code, "register")
        if not sent:
            return render_template("register.html", error=message)

        return redirect(f"/verify-register-otp?email={email}")

    return render_template("register.html")


@app.route("/verify-register-otp", methods=["GET", "POST"])
def verify_register_otp():
    email = request.values.get("email", "").strip().lower()
    if not email:
        return redirect("/register")

    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action", "verify")

        if action == "resend":
            pending = otp_requests.find_one({"email": email, "purpose": "register"})
            if not pending:
                return redirect("/register")

            otp_code = _create_otp_request(email, "register", pending.get("payload", {}))
            sent, send_msg = _send_otp_email(email, otp_code, "register")
            if sent:
                message = "A new OTP has been sent."
            else:
                error = send_msg
        else:
            otp_code = request.form.get("otp", "").strip()
            pending = _find_valid_otp_request(email, "register", otp_code)

            if not pending:
                error = "Invalid or expired OTP."
            else:
                payload = pending.get("payload", {})
                password = payload.get("password", "")

                if not password:
                    error = "Invalid registration request. Please register again."
                elif users.find_one({"email": email}):
                    error = "Email is already registered."
                else:
                    is_admin = _is_admin_email(email)
                    users.insert_one({
                        "email": email,
                        "password": password,
                        "email_verified": True,
                        "is_blocked": False,
                        "is_admin": is_admin,
                        "is_premium": False,
                        "language": [],
                        "language_play_counts": {},
                        "last_song": None,
                        "last_time": 0,
                        "created_at": datetime.utcnow()
                    })
                    otp_requests.delete_many({"email": email, "purpose": "register"})
                    return redirect("/")

    return render_template("verify_register_otp.html", email=email, message=message, error=error)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    message = None
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            error = "Enter your Gmail address."
            return render_template("forgot_password.html", error=error)

        if not _is_valid_gmail(email):
            error = "Please enter a valid Gmail address."
            return render_template("forgot_password.html", error=error)

        user = users.find_one({"email": email})
        if not user:
            error = "No account found for this email."
            return render_template("forgot_password.html", error=error)

        otp_code = _create_otp_request(email, "reset", {"email": email})
        sent, send_msg = _send_otp_email(email, otp_code, "reset")
        if not sent:
            error = send_msg
            return render_template("forgot_password.html", error=error)

        message = "OTP sent to your Gmail."
        return redirect(f"/reset-password?email={email}")

    return render_template("forgot_password.html", message=message, error=error)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():

    email = request.values.get("email", "").strip().lower()
    if not email:
        return redirect("/forgot-password")

    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action", "reset")

        if action == "resend":
            user = users.find_one({"email": email})
            if not user:
                return redirect("/forgot-password")

            otp_code = _create_otp_request(email, "reset", {"email": email})
            sent, send_msg = _send_otp_email(email, otp_code, "reset")
            if sent:
                message = "A new OTP has been sent."
            else:
                error = send_msg
        else:
            otp_code = request.form.get("otp", "").strip()
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not new_password:
                error = "New password is required."
            elif new_password != confirm_password:
                error = "Passwords do not match."
            else:
                valid = _find_valid_otp_request(email, "reset", otp_code)
                if not valid:
                    error = "Invalid or expired OTP."
                else:
                    users.update_one({"email": email}, {"$set": {"password": new_password}})
                    otp_requests.delete_many({"email": email, "purpose": "reset"})
                    return redirect("/")

    return render_template("reset_password.html", email=email, message=message, error=error)


# LANGUAGE
@app.route("/language", methods=["GET","POST"])
def language():
    need_login = _require_login_redirect()
    if need_login:
        return need_login

    current_user = _get_current_user()
    if not current_user:
        session.pop("user_email", None)
        return redirect("/")

    if request.method == "POST":
        selected_languages = [
            str(lang).strip().lower() for lang in request.form.getlist("language")
            if isinstance(lang, str) and lang.strip()
        ]

        if not selected_languages:
            single_language = request.form.get("language")
            if single_language:
                selected_languages = [str(single_language).strip().lower()]

        users.update_one(
            {"email": session["user_email"]},
            {"$set": {"language": selected_languages}}
        )

        return redirect("/playlist")

    selected_languages = _get_user_languages(current_user)
    return render_template(
        "language.html",
        selected_languages=selected_languages,
        available_languages=AVAILABLE_LANGUAGES
    )


# PLAYLIST
@app.route("/playlist")
def playlist():
    need_login = _require_login_redirect()
    if need_login:
        return need_login

    user = _get_current_user()
    if not user:
        session.pop("user_email", None)
        return redirect("/")

    videos = _get_prioritized_all_videos(user)
    # Debugging: ensure blocked videos are not returned to non-admin users
    try:
        if not _is_admin_user(user):
            blocked_returned = [v.get("youtube_url") for v in videos if v.get("blocked")]
            if blocked_returned:
                print("[debug.playlist] WARN: returning blocked videos to non-admin user:", blocked_returned[:20])
    except Exception as _e:
        print("[debug.playlist] error while checking blocked flags:", str(_e))
    is_premium = bool(user.get("is_premium", False))
    is_admin = _is_admin_user(user)
    return render_template("playlist.html", videos=videos, is_premium=is_premium, is_admin=is_admin)



# RANDOM NEXT
@app.route("/next-random")
def next_random():
    need_login = _require_login_redirect()
    if need_login:
        return ""

    user = _get_current_user()
    videos = _get_prioritized_all_videos(user or {})

    if not videos:
        return ""

    v = random.choice(videos)
    return v.get("youtube_url", "")



@app.route("/api/stream")
def api_stream():

    # 🔥 COMPLETELY REMOVE LOGIN CHECK
    # (NO _require_login_redirect at all)

    url = request.args.get("url")
    title = request.args.get("title")

    if not url:
        return jsonify({"error": "No url"}), 400

    data = get_stream(url, title=title)

    if not data or not data.get("stream_url"):
        return jsonify({
            "stream_url": "",
            "title": title or "",
            "thumbnail": "",
            "error": "Song unavailable"
        }), 200

    return jsonify({
        "stream_url": data.get("stream_url", ""),
        "title": data.get("title", title or ""),
        "thumbnail": data.get("thumbnail", "")
    }), 200






@app.route("/track-play", methods=["POST"])
def track_play():
    need_login = _require_login_redirect()
    if need_login:
        return "Unauthorized", 401

    url = request.form.get("url", "").strip()
    playlist_key = _safe_playlist_field_key(request.form.get("playlist_key", ""))
    if not url:
        return "", 204

    match = playlists.find_one({"videos.youtube_url": url}, {"language": 1})
    lang = ""
    if match:
        lang = str(match.get("language", "")).strip().lower()

    update_data = {
        "last_song": url,
        "last_time": int(datetime.utcnow().timestamp())
    }

    update_doc = {"$set": update_data}
    if lang:
        update_doc["$inc"] = {f"language_play_counts.{lang}": 1}

    if playlist_key:
        update_doc["$addToSet"] = {f"playlist_play_state.{playlist_key}.played_urls": url}

    users.update_one({"email": session["user_email"]}, update_doc)
    return "", 204


@app.route("/api/user-playlists", methods=["GET", "POST"])
def api_user_playlists():
    need_login = _require_login_redirect()
    if need_login:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    email = session.get("user_email", "").strip().lower()

    if request.method == "GET":
        # Build a canonical set of blocked video keys across all playlists so
        # we can hide blocked songs from user-created playlists.
        blocked_keys = set()
        for pdoc in playlists.find({}, {"videos": 1, "blocked_urls": 1}):
            blocked_keys.update(k for k in (_video_key(u) for u in (pdoc.get("blocked_urls") or [])) if k)
            for vv in (pdoc.get("videos") or []):
                if vv.get("blocked"):
                    k = _video_key(vv.get("youtube_url"))
                    if k:
                        blocked_keys.add(k)

        print("[debug.api_user_playlists] blocked_keys_count=", len(blocked_keys))

        docs = list(user_playlists.find({"user_email": email}).sort("created_at", -1))
        result = []
        for d in docs:
            ser = _serialize_user_playlist(d)
            original_count = len(d.get("songs") or [])
            filtered = [s for s in (d.get("songs") or []) if _video_key(s) not in blocked_keys]
            if original_count != len(filtered):
                print(f"[debug.api_user_playlists] playlist {ser.get('id')} filtered {original_count - len(filtered)} blocked songs")
            ser["songs"] = filtered
            result.append(ser)

        return jsonify({"ok": True, "playlists": result})

    action = request.form.get("action", "").strip().lower()
    if action == "create":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            return jsonify({"ok": False, "error": "Playlist name is required"}), 400

        created = {
            "user_email": email,
            "name": name,
            "description": description,
            "songs": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        result = user_playlists.insert_one(created)
        created["_id"] = result.inserted_id
        return jsonify({"ok": True, "playlist": _serialize_user_playlist(created)})

    if action == "delete":
        playlist_id = _safe_object_id(request.form.get("playlist_id", ""))
        if not playlist_id:
            return jsonify({"ok": False, "error": "Invalid playlist id"}), 400

        user_playlists.delete_one({"_id": playlist_id, "user_email": email})
        return jsonify({"ok": True})

    if action == "add_song":
        playlist_id = _safe_object_id(request.form.get("playlist_id", ""))
        song_url = request.form.get("song_url", "").strip()

        if not playlist_id or not song_url:
            return jsonify({"ok": False, "error": "Playlist and song are required"}), 400

        user_playlists.update_one(
            {"_id": playlist_id, "user_email": email},
            {
                "$addToSet": {"songs": song_url},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return jsonify({"ok": True})

    if action == "remove_song":
        playlist_id = _safe_object_id(request.form.get("playlist_id", ""))
        song_url = request.form.get("song_url", "").strip()

        if not playlist_id or not song_url:
            return jsonify({"ok": False, "error": "Playlist and song are required"}), 400

        user_playlists.update_one(
            {"_id": playlist_id, "user_email": email},
            {
                "$pull": {"songs": song_url},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "Unknown action"}), 400

# ADMIN
@app.route("/admin", methods=["GET","POST"])
def admin():
    need_login = _require_login_redirect()
    if need_login:
        return need_login

    current_user = _get_current_user()
    if not _is_admin_user(current_user):
        return redirect("/playlist")

    if _is_admin_email(current_user.get("email", "")) and not current_user.get("is_admin"):
        users.update_one(
            {"email": current_user.get("email", "").strip().lower()},
            {"$set": {"is_admin": True}}
        )

    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action", "import_playlist").strip().lower()

        if action == "import_playlist":
            url = request.form.get("url", "").strip()
            language = request.form.get("language", "").strip().lower()
            playlist_name = request.form.get("playlist_name", "").strip()

            if not url or not language or not playlist_name:
                error = "Playlist URL, language and playlist name are required."
            else:
                existing = playlists.find_one({
                    "language": language,
                    "playlist_name": playlist_name
                })

                if existing:
                    playlists.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {
                                "source_url": url,
                                "created_by": "admin",
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    message = "Playlist source updated. Songs will be fetched live each time."
                else:
                    playlists.insert_one({
                        "language": language,
                        "playlist_name": playlist_name,
                        "source_url": url,
                        "created_by": "admin",
                        "videos": [],
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })
                    message = "Playlist source saved. Songs will be fetched live each time."

        elif action == "import_song":
            language = request.form.get("song_language", "").strip().lower()
            playlist_name = request.form.get("song_playlist_name", "").strip()
            song_url = request.form.get("song_url", "").strip()
            song_title = request.form.get("song_title", "").strip()
            song_thumbnail = request.form.get("song_thumbnail", "").strip()

            if not language or not playlist_name or not song_url:
                error = "Song URL, language and playlist name are required."
            else:
                # Default song doc includes blocked flag (default False)
                song_doc = {
                    "title": song_title or song_url,
                    "youtube_url": song_url,
                    "thumbnail": song_thumbnail or _thumbnail_from_video_url(song_url),
                    "blocked": False
                }

                existing = playlists.find_one({
                    "language": language,
                    "playlist_name": playlist_name
                })

                if existing:
                    existing_keys = {
                        _video_key(v.get("youtube_url")) for v in existing.get("videos", []) if v.get("youtube_url")
                    }
                    # Normalize existing blocked urls for comparison
                    existing_blocked = set(k for k in (_video_key(u) for u in (existing.get("blocked_urls") or [])) if k)

                    # If playlist-level blocked_urls contains this URL key, preserve blocked state
                    if _video_key(song_url) in existing_blocked:
                        song_doc["blocked"] = True

                    if _video_key(song_url) in existing_keys:
                        message = "Song already exists in this playlist."
                    else:
                        playlists.update_one(
                            {"_id": existing["_id"]},
                            {"$push": {"videos": song_doc}, "$set": {"updated_at": datetime.utcnow()}}
                        )
                        message = "Song imported successfully."
                else:
                    playlists.insert_one({
                        "language": language,
                        "playlist_name": playlist_name,
                        "created_by": "admin",
                        "videos": [song_doc],
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    })
                    message = "Playlist created and song imported."

        elif action == "song_action":
            # Block / Unblock a specific song in an admin playlist
            playlist_id = _safe_object_id(request.form.get("playlist_id", ""))
            song_url = request.form.get("song_url", "").strip()
            op = request.form.get("op", "").strip().lower()
            # Validate inputs
            if not playlist_id or not song_url or op not in {"block", "unblock"}:
                error = "Invalid song action."
                print("[admin.song_action] Invalid input:", playlist_id, song_url, op)
                return jsonify({"ok": False, "error": error}), 400

            is_block = op == "block"
            print(f"[admin.song_action] playlist_id={playlist_id} song_url={song_url} op={op}")

            # Maintain playlist-level blocked_urls for source-based playlists.
            # Use canonical video keys so different URL formats match correctly.
            try:
                pl = playlists.find_one({"_id": playlist_id}, {"videos": 1, "blocked_urls": 1})
                if not pl:
                    return jsonify({"ok": False, "error": "Playlist not found."}), 404

                # build canonical blocked set
                blocked_set = set(k for k in (_video_key(u) for u in (pl.get("blocked_urls") or [])) if k)
                target_key = _video_key(song_url)
                if not target_key:
                    return jsonify({"ok": False, "error": "Invalid song URL."}), 400

                if is_block:
                    blocked_set.add(target_key)
                else:
                    blocked_set.discard(target_key)

                # persist blocked_urls as canonical keys
                res_block = playlists.update_one({"_id": playlist_id}, {"$set": {"blocked_urls": list(blocked_set), "updated_at": datetime.utcnow()}})

                # update videos array blocked flags consistently
                new_videos = []
                for vv in (pl.get("videos") or []):
                    vv2 = dict(vv)
                    vv_key = _video_key(vv2.get("youtube_url"))
                    vv2["blocked"] = bool(vv_key and vv_key in blocked_set)
                    new_videos.append(vv2)

                res_v = playlists.update_one({"_id": playlist_id}, {"$set": {"videos": new_videos, "updated_at": datetime.utcnow()}})
                print("[admin.song_action] update results:", getattr(res_block, 'raw_result', None), getattr(res_v, 'raw_result', None))
            except Exception as e:
                print("[admin.song_action] update error:", str(e))
                return jsonify({"ok": False, "error": "Database update failed."}), 500

            message = f"Song {'blocked' if is_block else 'unblocked'}."
            return jsonify({"ok": True, "message": message, "playlist_id": str(playlist_id), "song_url": song_url, "blocked": is_block})

        elif action == "user_action":
            target_email = request.form.get("target_email", "").strip().lower()
            op = request.form.get("op", "").strip().lower()

            if not target_email or op not in {"block", "unblock"}:
                error = "Invalid user action."
            else:
                users.update_one(
                    {"email": target_email},
                    {"$set": {"is_blocked": op == "block"}}
                )
                message = f"User {target_email} {'blocked' if op == 'block' else 'unblocked'}."

        elif action == "delete_playlist":
            playlist_id = _safe_object_id(request.form.get("playlist_id", ""))
            if not playlist_id:
                error = "Invalid playlist id."
            else:
                deleted = playlists.delete_one({"_id": playlist_id})
                if deleted.deleted_count:
                    message = "Playlist deleted successfully."
                else:
                    error = "Playlist not found."

        else:
            error = "Unknown admin action."

    all_users = list(users.find({"email": {"$exists": True}}, {"password": 0}).sort("created_at", -1))
    total_users = len(all_users)

    now_ts = int(datetime.utcnow().timestamp())
    live_users = sum(1 for u in all_users if int(u.get("last_time") or 0) >= now_ts - 900)

    admin_playlists = list(playlists.find({}, {"videos": 1, "language": 1, "playlist_name": 1, "created_by": 1, "updated_at": 1, "source_url": 1, "blocked_urls": 1}))
    admin_playlists_view = []
    total_admin_songs = 0
    for p in admin_playlists:
        source_url = str(p.get("source_url", "")).strip()
        stored_videos = p.get("videos", []) or []
        stored_blocked_map = { _video_key(v.get("youtube_url")): bool(v.get("blocked")) for v in stored_videos if v.get("youtube_url") }
        blocked_urls = set(k for k in (_video_key(u) for u in (p.get("blocked_urls") or [])) if k)

        if source_url:
            playlist_videos = _extract_playlist_live_cached(source_url, fallback_videos=stored_videos)
        else:
            playlist_videos = stored_videos

        songs_list = []
        for video in playlist_videos:
            if not video:
                continue
            v = dict(video)
            v["thumbnail"] = _resolve_thumbnail(v)
            video_key = _video_key(v.get("youtube_url")) or v.get("youtube_url")
            v["blocked"] = bool(stored_blocked_map.get(video_key) or (video_key in blocked_urls) or bool(v.get("blocked", False)))
            songs_list.append(v)

        p_view = dict(p)
        # Normalize id to string for templates and client-side matching
        try:
            p_view["_id"] = str(p_view.get("_id"))
        except Exception:
            pass
        p_view["songs"] = songs_list
        p_view["song_count"] = len(songs_list)
        admin_playlists_view.append(p_view)
        total_admin_songs += len(songs_list)

    return render_template(
        "admin.html",
        message=message,
        error=error,
        users_list=all_users,
        total_users=total_users,
        live_users=live_users,
        total_playlists=len(admin_playlists),
        total_songs=total_admin_songs,
        admin_playlists=admin_playlists_view,
        available_languages=AVAILABLE_LANGUAGES
    )
print("routes:")
print(app.url_map)

if __name__ == "__main__":
    app.run(debug=True) 