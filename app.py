from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import yt_dlp
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
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if 'url' in info and info['url']:
                direct_url = info['url']
            elif 'formats' in info and len(info['formats']) > 0:
                direct_url = info['formats'][-1]['url']
            else:
                return jsonify({"error": "No video found"}), 500
                
            return jsonify({
                "downloadUrl": direct_url,
                "title": info.get('title', 'video')
            })
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
