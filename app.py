
import os
import tempfile
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)

ALLOWED_PLATFORMS = {
    "tiktok": ["tiktok.com"],
    "instagram": ["instagram.com"],
    "facebook": ["facebook.com", "fb.watch"],
    "telegram": ["t.me", "telegram.org"],
    "moviebox": ["movie-box.com.ng"],
}


def detect_platform(url):
    try:
        hostname = (urlparse(url).hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]

        for platform, domains in ALLOWED_PLATFORMS.items():
            if any(
                hostname == domain or hostname.endswith("." + domain)
                for domain in domains
            ):
                return platform

        return None
    except Exception:
        return None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Please enter a video link."}), 400

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return jsonify({"error": "Please enter a valid link."}), 400

    platform = detect_platform(url)

    if not platform:
        return jsonify({
            "error": "This platform is not supported. YouTube is not supported."
        }), 400

    temp_dir = tempfile.mkdtemp(prefix="blackdownloader_")

    options = {
        "outtmpl": os.path.join(temp_dir, "%(title).150s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": 500 * 1024 * 1024,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.isfile(filename):
            files = [
                os.path.join(temp_dir, name)
                for name in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, name))
            ]
            if not files:
                raise FileNotFoundError("The downloaded file was not found.")
            filename = files[0]

        return send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename),
            mimetype="application/octet-stream",
        )

    except Exception as exc:
        app.logger.exception("Download failed for %s", platform)
        return jsonify({
            "error": "Download failed. The link may be private, unsupported, or temporarily unavailable."
        }), 422


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
