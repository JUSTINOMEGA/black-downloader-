from flask import Flask, request, jsonify, render_template
import yt_dlp
import os

app = Flask(__name__)

# For ad and stats
STATS = {"total_downloads": 12483, "online": 127}

def get_cookies_file():
    if os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/info")
def info():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "No URL"}), 400
    
    STATS["total_downloads"] += 1
    
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
    }
    cookie = get_cookies_file()
    if cookie:
        ydl_opts["cookiefile"] = cookie

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(url, download=False)
            
            formats = []
            # Best video
            if "formats" in data:
                # Get best mp4s
                best = []
                for f in data["formats"]:
                    if f.get("vcodec") != "none" and f.get("ext") in ["mp4", "m4a", "mp3"]:
                        qual = f.get("format_note") or f.get("height") or "HD"
                        formats.append({
                            "quality": f"{qual} - {f.get('ext')}",
                            "url": f.get("url"),
                            "ext": f.get("ext")
                        })
                formats = sorted(formats, key=lambda x: x["quality"], reverse=True)[:8]

            # Fallback direct url
            if not formats:
                formats.append({
                    "quality": "HD Video",
                    "url": data.get("url"),
                    "ext": "mp4"
                })
                formats.append({
                    "quality": "MP3 Audio",
                    "url": data.get("url"),
                    "ext": "mp3"
                })

            return jsonify({
                "title": data.get("title", "Black Video"),
                "thumbnail": data.get("thumbnail", ""),
                "formats": formats,
                "total": STATS["total_downloads"],
                "online": STATS["online"]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stats")
def stats():
    return jsonify(STATS)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
