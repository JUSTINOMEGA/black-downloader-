
import ipaddress
import os
import re
import shutil
import socket
import tempfile
from urllib.parse import urlparse

import requests
import yt_dlp
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Maximum download size: 500 MB
MAX_FILE_SIZE = 500 * 1024 * 1024

# MovieBox and social platforms may change their supported URLs.
PLATFORM_HOSTS = {
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "fb.watch",
    "telegram.org",
    "t.me",
    "movie-box.com.ng",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".webm", ".mkv"
}


def is_public_host(hostname):
    """Reject localhost, private IPs, and non-public DNS results."""
    if not hostname:
        return False

    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False

    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    hostname, None, type=socket.SOCK_STREAM
                )
            ]
        except (OSError, ValueError):
            return False

    return bool(addresses) and all(
        address.is_global for address in addresses
    )


def validate_url(url):
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False

    if parsed.username or parsed.password:
        return False

    return is_public_host(parsed.hostname)


def detect_platform(url):
    host = (urlparse(url).hostname or "").lower()
    host = host.removeprefix("www.")

    if host == "vm.tiktok.com" or host.endswith(".tiktok.com") or host == "tiktok.com":
        return "TikTok"

    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "Instagram"

    if host == "facebook.com" or host.endswith(".facebook.com") or host == "fb.watch":
        return "Facebook"

    if host == "t.me" or host.endswith(".telegram.org") or host == "telegram.org":
        return "Telegram"

    if host == "movie-box.com.ng" or host.endswith(".movie-box.com.ng"):
        return "MovieBox"

    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/download", methods=["GET", "POST"])
def download_api():
    if request.method == "POST":
        video_url = (request.get_json(silent=True) or {}).get("url", "").strip()
    else:
        video_url = request.args.get("url", "").strip()

    if not video_url:
        return jsonify({"error": "Please paste a video link."}), 400

    if len(video_url) > 4096 or not validate_url(video_url):
        return jsonify({"error": "Invalid or unsupported URL."}), 400

    platform = detect_platform(video_url)

    parsed = urlparse(video_url)
    path = parsed.path.lower()
    is_direct_video = any(
        path.endswith(ext) for ext in VIDEO_EXTENSIONS
    )

    # Accept direct video URLs only for known public platform domains
    # or publicly hosted video files. Do not allow arbitrary local URLs.
    if not platform and not is_direct_video:
        return jsonify({
            "error": (
                "This link is not from a supported platform. "
                "Use TikTok, Instagram, Facebook, Telegram, or MovieBox."
            )
        }), 400

    temp_dir = tempfile.mkdtemp(prefix="black_downloader_")

    try:
        output_template = os.path.join(temp_dir, "%(title).100B.%(ext)s")

        options = {
            "outtmpl": output_template,
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "max_filesize": MAX_FILE_SIZE,
            "max_downloads": 1,
            "socket_timeout": 25,
            "retries": 2,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "ignoreerrors": False,
        }

        # yt-dlp may not support every Telegram post or MovieBox page.
        # Private/restricted content is not bypassed.
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([video_url])

        files = [
            os.path.join(temp_dir, name)
            for name in os.listdir(temp_dir)
            if os.path.isfile(os.path.join(temp_dir, name))
        ]

        if not files:
            raise RuntimeError(
                "No video file was downloaded. The link may be unsupported."
            )

        file_path = max(files, key=os.path.getsize)

        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            raise RuntimeError("The video exceeds the 500 MB download limit.")

        original_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(original_name)[0]
        safe_name = secure_filename(name_without_ext) or "video"
        ext = os.path.splitext(original_name)[1].lower()

        if ext not in VIDEO_EXTENSIONS:
            ext = ".mp4"

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=f"{safe_name}{ext}",
            conditional=True,
        )

        response.call_on_close(
            lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )
        return response

    except Exception:
        app.logger.exception(
            "Download failed for platform %s", platform or "direct video"
        )
        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            "error": (
                "Download failed. This source may be unsupported, "
                "unavailable, private, or restricted. Try another "
                "public video link."
            )
        }), 502


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
