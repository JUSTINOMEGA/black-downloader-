from flask import Flask, request, jsonify, render_template
import yt_dlp
import requests

app = Flask(__name__)

# Only allow these
ALLOWED = ["facebook.com", "fb.watch", "tiktok.com", "instagram.com", "moviebox", "movb", "fb.com"]

COBALT_API = "https://api.cobalt.tools/api/json"
COBALT = ["facebook.com", "fb.watch", "tiktok.com", "instagram.com", "fb.com"]

def is_allowed(url):
    url = url.lower()
    return any(x in url for x in ALLOWED)

def cobalt_download(url):
    try:
        r = requests.post(COBALT_API, json={"url": url, "vCodec": "h264", "vQuality": "720"}, 
                           headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=15)
        data = r.json()
        if data.get("status") in ["redirect","tunnel","picker"]:
            return data.get("url")
    except:
        pass
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/info")
def info():
    url = request.args.get("url","")
    if not url or not is_allowed(url):
        return jsonify({"error":"Only Facebook, TikTok, Instagram and MovieBox links allowed"}), 400

    # FB / IG / TikTok via Cobalt
    if any(x in url.lower() for x in COBALT):
        direct = cobalt_download(url)
        if direct:
            return jsonify({
                "title": "Video",
                "thumbnail": "",
                "formats": [{"format_id":"cobalt","ext":"mp4","quality":"720p - MP4","url":direct}]
            })

    # MovieBox via yt-dlp
    try:
        ydl_opts = {'quiet': True, 'noplaylist': True, 'nocheckcertificate': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get("formats", [])[-10:]:
                if f.get("url"):
                    formats.append({
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "quality": f"{f.get('height','')}p - {f.get('ext')}",
                        "url": f.get("url")
                    })
            return jsonify({
                "title": info.get("title","MovieBox Video"),
                "thumbnail": info.get("thumbnail",""),
                "formats": formats[::-1]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
