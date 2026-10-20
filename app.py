from flask import Flask, render_template_string, request, jsonify, send_file, session
import yt_dlp
import os
import tempfile

app = Flask(__name__)
app.secret_key = "final"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")

print(f"Cookies exists? {os.path.exists(COOKIE_FILE)}")

HTML = """
<!DOCTYPE html>
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Black Downloader</title>
<style>
body{background:#0a0a0a;color:white;font-family:Arial;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}
.box{background:#1a1a1a;padding:25px;border-radius:12px;width:90%;max-width:450px}
input{width:100%;padding:12px;border-radius:8px;border:none;margin:12px 0;box-sizing:border-box}
button{width:100%;padding:12px;background:#00ff88;border:none;border-radius:8px;font-weight:bold}
#s{margin-top:15px;text-align:center;word-break:break-all}
a{color:#00ff88}
</style>
</head>
<body>
<div class="box">
<h3 style="text-align:center">Black Downloader 🔥</h3>
<input id="url" placeholder="Paste YouTube link">
<button onclick="go()">Download</button>
<div id="s"></div>
</div>
<script>
async function go(){
 let u=document.getElementById('url').value;
 if(!u){alert('Paste URL');return}
 document.getElementById('s').innerHTML='⏳ Downloading...';
 let r=await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:u})});
 let d=await r.json();
 if(d.error){document.getElementById('s').innerHTML='❌ '+d.error}
 else{document.getElementById('s').innerHTML='✅ Ready! <a href="/getfile">Click to Save</a>'}
}
</script>
</body>
</html>
"""

def get_opts():
    opts = {
        'format': 'best[height<=720][ext=mp4]/best',
        'noplaylist': True,
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'extractor_args': {'youtube': {'player_client': ['android','ios','web']}},
        'quiet': True,
    }
    if os.path.exists(COOKIE_FILE):
        opts['cookiefile'] = COOKIE_FILE
        print(f"Using cookies: {COOKIE_FILE}")
    return opts

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/download', methods=['POST'])
def download():
    url = request.get_json().get('url','').strip()
    if not url:
        return jsonify({'error':'No URL'})
    try:
        opts = get_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(info)
            session['file'] = file
            return jsonify({'ok':True})
    except Exception as e:
        print(str(e))
        return jsonify({'error': str(e)})

@app.route('/getfile')
def getfile():
    f = session.get('file')
    if f and os.path.exists(f):
        return send_file(f, as_attachment=True)
    return "File not found, try again", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
