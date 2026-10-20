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

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(url, download=False)
            formats = []
            if 'formats' in data:
                seen = set()
                for f in data.get('formats', [])[-15:]:
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
        return jsonify({"error": f"Cannot download this link: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
