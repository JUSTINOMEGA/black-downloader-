from flask import Flask, request, jsonify, render_template
import yt_dlp
import os
import random

app = Flask(__name__)

# Stats for UI
STATS = {"total_downloads": 12483, "online": 127}

def get_cookies_file():
    # If cookies.txt dey, use am. If e no dey, work without am.
    if os.path.exists("cookies.txt"):
        return "cookies.txt"
    if os.path.exists("fb_cookies.txt"):
        return "fb_cookies.txt"
    return None

@app.route("/")
def index():
    # Random online for live effect
    STATS["online"] = random.randint(95, 210)
    return render_template("index.html", online=STATS["online"], total=STATS["total_downloads"])

@app.route("/info")
def info():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL pasted"}), 400
    
    # Add https if user no add am (for telegram etc)
    if not url.startswith("http"):
        url = "https://" + url

    STATS["total_downloads"] += 1

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "format": "best",
    }

    cookie = get_cookies_file()
    if cookie:
        ydl_opts["cookiefile"] = cookie

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(url, download=False)
            
            # Handle playlist - take first video
            if "entries" in data:
                data = data["entries"][0]

            formats_list = []
            
            if "formats" in data and data["formats"]:
                seen = set()
                for f in data["formats"]:
                    ext = f.get("ext", "mp4")
                    height = f.get("height")
                    vcodec = f.get("vcodec")
                    
                    # Video formats
                    if vcodec != "none" and height:
                        key = f"{height}p"
                        if key not in seen:
                            formats_list.append({
                                "quality": f"{height}p HD" if height >= 720 else f"{height}p",
                                "url": f.get("url"),
                                "ext": ext,
                                "height": height
                            })
                            seen.add(key)
                
                # Sort high to low
                formats_list = sorted(formats_list, key=lambda x: x.get("height",0), reverse=True)
            
            # Fallback - direct url
            if not formats_list:
                direct_url = data.get("url") or (data.get("formats", [{}])[0].get("url") if data.get("formats") else None)
                if direct_url:
                    formats_list.append({"quality": "HD Video", "url": direct_url, "ext": "mp4", "height": 720})
                    formats_list.append({"quality": "MP3 Audio", "url": direct_url, "ext": "mp3", "height": 0})
            
            # Cut to 6 best
            formats_list = formats_list[:6]

            if not formats_list:
                return jsonify({"error": "No download links found for this platform"}), 400

            return jsonify({
                "title": data.get("title", "Black Video"),
                "thumbnail": data.get("thumbnail", ""),
                "formats": formats_list,
                "total": STATS["total_downloads"],
                "online": random.randint(95, 210)
            })

    except Exception as e:
        err = str(e)
        # Cleaner error for user
        if "Unsupported URL" in err:
            return jsonify({"error": "This link not supported yet"}), 400
        if "Private" in err or "login" in err.lower():
            return jsonify({"error": "This video is private. Make it public first."}), 400
        return jsonify({"error": err}), 500

@app.route("/stats")
def stats():
    return jsonify(STATS)

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
