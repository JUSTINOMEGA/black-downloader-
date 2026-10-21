
import ipaddress
import os
import shutil
import socket
import tempfile
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

MAX_FILE_SIZE = 500 * 1024 * 1024

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".webm", ".mkv"
}


def is_public_host(host):
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            results = socket.getaddrinfo(
                host, None, type=socket.SOCK_STREAM
            )
            addresses = list({
                ipaddress.ip_address(item[4][0])
                for item in results
            })
        except (OSError, ValueError):
            return False

    return bool(addresses) and all(
        address.is_global for address in addresses
    )


def validate_url(url):
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        if not parsed.hostname or parsed.username or parsed.password:
            return False

        if not is_public_host(parsed.hostname):
            return False

        return True
    except (ValueError, TypeError):
        return False


def detect_platform(url):
    host = (urlparse(url).hostname or "").lower()
    host = host.removeprefix("www.")

    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        return "TikTok"

    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "Instagram"

    if (
        host == "facebook.com"
        or host.endswith(".facebook.com")
        or host == "fb.watch"
    ):
        return "Facebook"

    if host == "t.me" or host == "telegram.org" or host.endswith(".telegram.org"):
        return "Telegram"

    if host == "movie-box.com.ng" or host.endswith(".movie-box.com.ng"):
        return "MovieBox"

    return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "yt_dlp_version": yt_dlp.version.__version__
    })


@app.route("/api/download", methods=["GET", "POST"])
def download_api():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        video_url = str(data.get("url", "")).strip()
    else:
        video_url = request.args.get("url", "").strip()

    if not video_url:
        return jsonify({
            "error": "Please paste a video link."
        }), 400

    if len(video_url) > 4096 or not validate_url(video_url):
        return jsonify({
            "error": "Invalid or inaccessible URL. Please check the link."
        }), 400

    platform = detect_platform(video_url)
    parsed = urlparse(video_url)

    is_direct_video = any(
        parsed.path.lower().endswith(ext)
        for ext in VIDEO_EXTENSIONS
    )

    if not platform and not is_direct_video:
        return jsonify({
            "error": (
                "Unsupported link. Use TikTok, Instagram, Facebook, "
                "Telegram, MovieBox, or a direct video URL."
            )
        }), 400

    temp_dir = tempfile.mkdtemp(prefix="black_downloader_")

    try:
        output_template = os.path.join(
            temp_dir, "%(title).100B.%(ext)s"
        )

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
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                )
            },
        }

        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(
                video_url, download=True
            )

        if not info:
            raise RuntimeError("No video information was returned.")

        files = [
            os.path.join(temp_dir, name)
            for name in os.listdir(temp_dir)
            if os.path.isfile(os.path.join(temp_dir, name))
        ]

        if not files:
            raise RuntimeError(
                "The source did not produce a downloadable video file."
            )

        file_path = max(files, key=os.path.getsize)
        file_size = os.path.getsize(file_path)

        if file_size == 0:
            raise RuntimeError("The downloaded file is empty.")

        if file_size > MAX_FILE_SIZE:
            raise RuntimeError("The video exceeds the 500 MB limit.")

        original_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(original_name)[0]
        ext = os.path.splitext(original_name)[1].lower()

        if ext not in VIDEO_EXTENSIONS:
            ext = ".mp4"

        safe_name = secure_filename(name_without_ext) or "video"

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=f"{safe_name}{ext}",
            conditional=True
        )

        response.call_on_close(
            lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )

        return response

    except Exception:
        app.logger.exception(
            "Download failed for platform %s",
            platform or "direct video"
        )

        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            "error": (
                "Download failed. The link may be private, unsupported, "
                "restricted, or blocked by the source. Try another "
                "public video link."
            )
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
