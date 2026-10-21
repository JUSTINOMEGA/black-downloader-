from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/download')
def download_api():
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({"error": "No URL"}), 400
    try:
        api_url = f"https://www.tikwm.com/api/?url={video_url}&count=12&cursor=0&web=1&hd=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(api_url, headers=headers, timeout=15)
        data = res.json()
        if data.get("code") == 0 and "data" in data:
            direct_url = data["data"].get("hdplay") or data["data"].get("play")
            title = data["data"].get("title", "video")
            return jsonify({"downloadUrl": direct_url, "title": title, "proxyUrl": f"/api/file?url={direct_url}&title={title}"})
        return jsonify({"error": "Failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/file')
def proxy_file():
    file_url = request.args.get('url')
    title = request.args.get('title', 'video')
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tikwm.com/"}
    r = requests.get(file_url, headers=headers, stream=True, timeout=30)
    return Response(r.iter_content(chunk_size=8192),
                    content_type='video/mp4',
                    headers={"Content-Disposition": f"attachment; filename={title}.mp4"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
