
import ipaddress
import logging
import os
import shutil
import socket
import tempfile
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

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
ALLOWED_SCHEMES = {"http", "https"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm", ".mkv"}
AUDIO_EXTENSIONS = {".mp3"}

PLATFORM_HOSTS = {
    "TikTok": ("tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
    "Instagram": ("instagram.com", "www.instagram.com"),
    "Facebook": ("facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"),
    "Telegram": ("t.me", "telegram.me", "telegram.org", "www.telegram.org"),
    "MovieBox": ("movie-box.com.ng", "www.movie-box.com.ng"),
    "Direct": (),
}


def validate_url(url):
    """Basic URL validation. Reject private/local destination hosts."""
    if not isinstance(url, str) or len(url) > 4096:
        return False, "Please provide a valid URL."

    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, "Only HTTP and HTTPS links are supported."

        if not parsed.hostname or parsed.username or parsed.password:
            return False, "The link is invalid."

        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False, "That host is not allowed."

        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            try:
                addresses = {
                    ipaddress.ip_address(result[4][0].split("%")[0])
                    for result in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
                }
            except (OSError, ValueError):
                return False, "The website could not be reached."

        if not addresses:
            return False, "The website could not be reached."

        for address in addresses:
            if not address.is_global:
                return False, "Links to private or local networks are not allowed."

        return True, ""
    except Exception:
        return False, "The link is invalid."


def host_matches(host, domain):
    return host == domain or host.endswith("." + domain)


def detect_platform(url):
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    for platform, domains in PLATFORM_HOSTS.items():
        if platform == "Direct":
            continue
        if any(host_matches(host, domain) for domain in domains):
            return platform
    return "Direct"


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "yt_dlp_version": yt_dlp.version.__version__,
    })


@app.route("/api/download", methods=["POST", "GET"])
def download_video():
    if request.method == "GET":
        url = request.args.get("url", "").strip()
        platform = request.args.get("platform", "").strip()
        mode = request.args.get("mode", "best").strip().lower()
    else:
        data = request.get_json(silent=True) or {}
        url = str(data.get("url", "")).strip()
        platform = str(data.get("platform", "")).strip()
        mode = str(data.get("mode", "best")).strip().lower()

    if not url:
        return jsonify({"error": "Please paste a video link."}), 400

    valid, reason = validate_url(url)
    if not valid:
        return jsonify({"error": reason}), 400

    detected = detect_platform(url)

    # Do not trust a user-selected platform label to bypass URL checks.
    if detected != "Direct" and platform and platform != detected:
        app.logger.info("Selected platform differs from detected platform.")

    if mode not in {"best", "fast", "audio"}:
        return jsonify({"error": "Select a supported download mode."}), 400

    if mode == "audio" and not shutil.which("ffmpeg"):
        return jsonify({
            "error": "MP3 conversion is not available yet because FFmpeg is not installed on the server."
        }), 501

    temp_dir = tempfile.mkdtemp(prefix="black_downloader_")
    output_template = os.path.join(temp_dir, "%(title).100B-%(id)s.%(ext)s")

    if mode == "audio":
        format_selector = "bestaudio/best"
    elif mode == "fast":
        # Prefer a single downloadable file to avoid a merge step.
        format_selector = "best[ext=mp4]/best"
    else:
        format_selector = "best[ext=mp4]/best"

    options = {
        "outtmpl": output_template,
        "format": format_selector,
        "noplaylist": True,
        "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 30,
        "retries": 2,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "ignoreerrors": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        },
    }

    if mode == "audio":
        options["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.extract_info(url, download=True)

        files = [
            path for path in Path(temp_dir).iterdir()
            if path.is_file() and path.suffix.lower() != ".part"
        ]

        if mode == "audio":
            files = [path for path in files if path.suffix.lower() in AUDIO_EXTENSIONS]
        else:
            files = [path for path in files if path.suffix.lower() in VIDEO_EXTENSIONS]

        if not files:
            raise FileNotFoundError(
                "No supported output file was created. This link may be unsupported."
            )

        output_file = max(files, key=lambda path: path.stat().st_size)

        if output_file.stat().st_size <= 0:
            raise ValueError("The downloaded file is empty.")

        if output_file.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("The downloaded file exceeds the 500 MB limit.")

        response = send_file(
            output_file,
            as_attachment=True,
            download_name=secure_filename(output_file.name),
            mimetype="audio/mpeg" if mode == "audio" else "application/octet-stream",
            conditional=False,
        )

        # Keep the temporary file alive while Flask sends it.
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response

    except Exception as exc:
        app.logger.exception("Download failed")
        shutil.rmtree(temp_dir, ignore_errors=True)

        message = str(exc)
        if "Unsupported URL" in message:
            message = "This website or link is not supported."
        elif "Private video" in message or "login" in message.lower():
            message = "This video may be private or require login access."
        elif "max-filesize" in message.lower() or "file size" in message.lower():
            message = "This file exceeds the download size limit."
        elif isinstance(exc, FileNotFoundError):
            message = str(exc)

        return jsonify({"error": message[:400]}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
