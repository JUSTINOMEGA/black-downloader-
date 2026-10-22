
import os
import re
import shutil
import tempfile
import threading
import ipaddress
import socket
from urllib.parse import urlparse, unquote

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    after_this_request,
)
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["JSON_SORT_KEYS"] = False

DOWNLOADS_DIR = os.path.join(tempfile.gettempdir(), "black_video_downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Prevent excessive simultaneous downloads on a small hosting instance.
download_slots = threading.BoundedSemaphore(2)

SUPPORTED_HOSTS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "fb.watch",
    "twitter.com",
    "x.com",
    "vimeo.com",
    "dailymotion.com",
    "reddit.com",
    "twitch.tv",
    "streamable.com",
    "pinterest.com",
    "soundcloud.com",
)

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"
}


def is_allowed_public_host(host):
    """Reject localhost and IP literals that are not public addresses."""
    if not host:
        return False

    host = host.lower().rstrip(".")

    if host == "localhost" or host.endswith(".localhost"):
        return False

    try:
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        pass

    try:
        addresses = socket.getaddrinfo(
            host, None, type=socket.SOCK_STREAM
        )
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0]).is_global
            for item in addresses
        )
    except (OSError, ValueError):
        return False


def detect_platform(url):
    """Recognize common video platforms and direct video URLs."""
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        path = unquote(parsed.path).lower()
    except (ValueError, AttributeError):
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    if not is_allowed_public_host(host):
        return None

    for domain in SUPPORTED_HOSTS:
        if host == domain or host.endswith("." + domain):
            if domain in ("youtube.com", "youtu.be",
                          "youtube-nocookie.com"):
                return "YouTube"
            if domain == "tiktok.com":
                return "TikTok"
            if domain == "instagram.com":
                return "Instagram"
            if domain in ("facebook.com", "fb.watch"):
                return "Facebook"
            if domain in ("twitter.com", "x.com"):
                return "X / Twitter"
            if domain == "vimeo.com":
                return "Vimeo"
            if domain == "dailymotion.com":
                return "Dailymotion"
            if domain == "reddit.com":
                return "Reddit"
            if domain == "twitch.tv":
                return "Twitch"
            if domain == "streamable.com":
                return "Streamable"
            if domain == "pinterest.com":
                return "Pinterest"
            if domain == "soundcloud.com":
                return "SoundCloud"

    if os.path.splitext(path)[1] in VIDEO_EXTENSIONS:
        return "Direct video"

    return None


def valid_url(url):
    if not isinstance(url, str) or not url.strip():
        return False

    if len(url) > 2048:
        return False

    parsed = urlparse(url.strip())

    return (
        parsed.scheme in ("http", "https")
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
    )


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Black Video Downloader"
    })


@app.route("/api/download", methods=["POST"])
def download_video():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not valid_url(url):
        return jsonify({
            "success": False,
            "error": "Please enter a valid video URL."
        }), 400

    platform = detect_platform(url)

    if not platform:
        return jsonify({
            "success": False,
            "error": (
                "This link is not from a recognized platform "
                "or direct video file."
            )
        }), 400

    if not download_slots.acquire(blocking=False):
        return jsonify({
            "success": False,
            "error": "The downloader is busy. Please try again shortly."
        }), 429

    workdir = tempfile.mkdtemp(prefix="download_", dir=DOWNLOADS_DIR)

    try:
        options = {
            "outtmpl": os.path.join(
                workdir, "%(title).80s-%(id)s.%(ext)s"
            ),
            "format": "best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 2,
            "fragment_retries": 2,
            "socket_timeout": 25,
            "max_filesize": 500 * 1024 * 1024,
            "restrictfilenames": True,
        }

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title") or "video"

        files = [
            os.path.join(workdir, name)
            for name in os.listdir(workdir)
            if os.path.isfile(os.path.join(workdir, name))
            and not name.endswith((".part", ".ytdl", ".json"))
        ]

        if not files:
            raise DownloadError(
                "The download finished without producing a video file."
            )

        # Prefer the largest completed file.
        filepath = max(files, key=os.path.getsize)
        extension = os.path.splitext(filepath)[1].lower()

        if extension not in VIDEO_EXTENSIONS:
            raise DownloadError(
                "The downloaded file is not a supported video format."
            )

        safe_title = re.sub(r'[\\/:*?"<>|]+', "_", title).strip()
        safe_title = safe_title[:100] or "video"
        filename = f"{safe_title}{extension}"

        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype="application/octet-stream",
            conditional=False,
        )

        # Clean up temporary files after the response is closed.
        response.call_on_close(
            lambda: shutil.rmtree(workdir, ignore_errors=True)
        )
        response.call_on_close(download_slots.release)

        return response

    except DownloadError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        download_slots.release()

        message = str(exc)
        print("yt-dlp download error:", message)

        if "Unsupported URL" in message:
            message = (
                "This URL is not supported by the current yt-dlp version."
            )
        elif "Sign in" in message or "login" in message.lower():
            message = (
                "This video requires authentication. "
                "Try a publicly accessible video you have permission to download."
            )
        elif "Private video" in message:
            message = "This video is private and cannot be downloaded publicly."
        else:
            message = (
                "The download failed. The platform may have changed "
                "its requirements, or the video may be unavailable. "
                "Try again later."
            )

        return jsonify({
            "success": False,
            "error": message
        }), 422

    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        download_slots.release()

        print("Unexpected download error:", repr(exc))

        return jsonify({
            "success": False,
            "error": "Something went wrong. Please try again later."
        }), 500


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "success": False,
        "error": "The submitted request is too large."
    }), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
