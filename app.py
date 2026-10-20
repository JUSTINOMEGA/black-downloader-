from flask import Flask, request, jsonify, render_template
import yt_dlp
import os
import time
import threading

app = Flask(__name__)

stats_file = "stats.txt"
online_users = {}
lock = threading.Lock()

def get_stats():
    if not os.path.exists(stats_file):
        return 0
    try:
        with open(stats_file, 'r') as f:
            return int(f.read().strip() or 0)
    except:
        return 0

def add_download():
    with lock:
        count = get_stats() + 1
        with open(stats_file, 'w') as f:
            f.write(str(count))

def track_online(ip):
    with lock:
        online_users[ip] = time.time()
        now = time.time()
        for k in list(online_users.keys()):
            if now - online_users[k] > 300:
                del online_users[k]
        return len(online_users)

@app.route('/')
def index():
    ip = request.remote_addr
    online = track_online(ip)
    total = get_stats()
    return render_template('index.html', online=online, total=total)

@app.route('/info')
def info():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # BLOCK YOUTUBE
    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        return jsonify({"error": "YouTube download is disabled. Please use TikTok, Facebook, Instagram or Twitter links."}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'http_headers': {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.tiktok.com/',
        },
        'extractor_args': {
            'tiktok': {
                'api_hostname': ['m.tiktok.com'],
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(url, download=False)
            formats = []
            if 'formats' in data and data['formats']:
                seen = set()
                for f in data.get('formats', [])[-20:]:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url'):
                        q = f.get('height')
                        quality = f"{q}p" if q else f.get('format_id', 'MP4')
                        if quality not in seen:
                            formats.append({
                                "quality": quality,
                                "ext": f.get('ext', 'mp4'),
                                "url": f.get('url')
                            })
                            seen.add(quality)
                formats = formats[-5:][::-1]
                if not formats:
                    formats = [{
                        "quality": "Best",
                        "ext": data.get('ext', 'mp4'),
                        "url": data.get('url')
                    }]
            else:
                formats = [{
                    "quality": "Best",
                    "ext": data.get('ext', 'mp4'),
                    "url": data.get('url')
                }]

            add_download()

            return jsonify({
                "title": data.get('title', 'Video'),
                "thumbnail": data.get('thumbnail', ''),
                "formats": formats
            })

    except Exception as e:
        err = str(e)
        if "TikTok" in err or "tiktok" in url.lower():
            return jsonify({"error": "TikTok is updating their system. Please try Facebook, Instagram or Twitter link - they work 100%."}), 500
        return jsonify({"error": f"Cannot download this link: {err}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
