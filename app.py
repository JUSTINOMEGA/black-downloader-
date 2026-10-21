
import os
import re
import time
import uuid
import shutil
import socket
import sqlite3
import tempfile
import ipaddress
import logging
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

MAX_FILE_SIZE = 500 * 1024 * 1024
LIVE_DB = os.path.join(tempfile.gettempdir(), "black_downloader_live.db")
LIVE_WINDOW = 45

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".webm", ".mkv"
}


# ---------- Live visitor database ----------

def init_live_db():
    with sqlite3.connect(LIVE_DB, timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visitors (
                visitor_id TEXT PRIMARY KEY,
                last_seen REAL NOT NULL
            )
        """)


init_live_db()


@app.route("/api/heartbeat", methods=["POST"])
def live_heartbeat():
    data = request.get_json(silent=True) or {}
    raw_id = data.get("visitor_id", "")

    try:
        visitor_id = str(uuid.UUID(str(raw_id)))
    except (ValueError, TypeError, AttributeError):
        return jsonify({"error": "Invalid visitor ID"}), 400

    now = time.time()

    try:
        with sqlite3.connect(LIVE_DB, timeout=10) as conn:
            conn.execute("""
                INSERT INTO visitors (visitor_id, last_seen)
                VALUES (?, ?)
                ON CONFLICT(visitor_id)
                DO UPDATE SET last_seen = excluded.last_seen
            """, (visitor_id, now))

            conn.execute(
                "DELETE FROM visitors WHERE last_seen < ?",
                (now - 120,)
            )

            count = conn.execute(
                "SELECT COUNT(*) FROM visitors WHERE last_seen >= ?",
                (now - LIVE_WINDOW,)
            ).fetchone()[0]

        return jsonify({"active_users": count})

    except sqlite3.Error:
        app.logger.exception("Live visitor tracking failed")
        return jsonify({"active_users": None}), 503


@app.route("/api/live-users", methods=["GET"])
def live_users():
    try:
        cutoff = time.time() - LIVE_WINDOW

        with sqlite3.connect(LIVE_DB, timeout=10) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM visitors WHERE last_seen >= ?",
                (cutoff,)
            ).fetchone()[0]

        return jsonify({"active_users": count})

    except sqlite3.Error:
        app.logger.exception("Could not count visitors")
        return jsonify({"active_users": None}), 503


# ---------- URL validation ----------

def validate_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return False

    try:
        parsed = urlparse(value.strip())

        if parsed.scheme not in ("http", "https"):
            return False

        if not parsed.hostname or parsed.username or parsed.password:
            return False

        host = parsed.hostname.lower()

        if host in ("localhost", "localhost.localdomain"):
            return False

        # Reject private, loopback and reserved IP addresses.
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_global
        except ValueError:
            pass

        # Reject domains that resolve to non-public IP addresses.
        addresses = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM
        )

        if not addresses:
            return False

        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                return False

        return True

    except (ValueError, OSError, socket.gaierror):
        return False


def detect_platform(url):
    host = urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.")

    if host.endswith("tiktok.com"):
        return "TikTok"
    if host.endswith("instagram.com"):
        return "Instagram"
    if host.endswith("facebook.com") or host.endswith("fb.watch"):
        return "Facebook"
    if host.endswith("t.me") or host.endswith("telegram.org"):
        return "Telegram"
    if host.endswith("movie-box.com.ng"):
        return "MovieBox"

    return "Direct"


# ---------- Main pages ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "yt_dlp_version": yt_dlp.version.__version__
    })


# ---------- Download endpoint ----------

@app.route("/api/download", methods=["POST"])
def download_video():
    data = request.get_json(silent=True) or {}

    video_url = str(data.get("url", "")).strip()
    selected_platform = str(data.get("platform", "Direct")).strip()

    if not validate_url(video_url):
        return jsonify({
            "error": "Please enter a valid public HTTP or HTTPS video link."
        }), 400

    platform = detect_platform(video_url)

    allowed_platforms = {
        "TikTok", "Instagram", "Facebook",
        "Telegram", "MovieBox", "Direct"
    }

    if selected_platform not in allowed_platforms:
        return jsonify({"error": "Invalid platform selection."}), 400

    # Accept supported platform URLs or links ending in a video extension.
    suffix = Path(urlparse(video_url).path).suffix.lower()

    if platform == "Direct" and suffix not in VIDEO_EXTENSIONS:
        return jsonify({
            "error": "This link is not from a recognized platform or direct video file."
        }), 400

    temp_dir = tempfile.mkdtemp(prefix="black_downloader_")
    output_template = os.path.join(temp_dir, "%(title).150B-%(id)s.%(ext)s")

    options = {
        "outtmpl": output_template,
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 30,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "nocheckcertificate": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        }
    }

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(video_url, download=True)
            prepared_path = downloader.prepare_filename(info)

        candidates = []

        if os.path.isfile(prepared_path):
            candidates.append(prepared_path)

        # yt-dlp may change the extension after downloading or merging.
        for path in Path(temp_dir).iterdir():
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                if str(path) not in candidates:
                    candidates.append(str(path))

        if not candidates:
            raise RuntimeError(
                "No downloadable video file was produced for this link."
            )

        file_path = max(candidates, key=os.path.getsize)
        file_size = os.path.getsize(file_path)

        if file_size == 0:
            raise RuntimeError("The downloaded file is empty.")

        if file_size > MAX_FILE_SIZE:
            raise RuntimeError("The video exceeds the 500 MB limit.")

        filename = secure_filename(os.path.basename(file_path))
        if not filename:
            filename = "black-downloader-video" + Path(file_path).suffix

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            conditional=False
        )

        response.call_on_close(
            lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )

        return response

    except Exception as error:
        app.logger.exception("Video download failed")
        shutil.rmtree(temp_dir, ignore_errors=True)

        message = str(error)

        if "Unsupported URL" in message:
            message = "This link is not supported."
        elif "private" in message.lower():
            message = "This video is private or unavailable."
        elif "max_filesize" in message.lower() or "file is larger" in message.lower():
            message = "The video exceeds the 500 MB limit."
        else:
            message = (
                "Download failed. The link may be unsupported, "
                "private, or temporarily blocked by the platform."
            )

        return jsonify({"error": message}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
