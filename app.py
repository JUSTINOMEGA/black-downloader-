from flask import Flask, render_template_string, request, jsonify, send_file, session
import yt_dlp
import os
import json
import tempfile

app = Flask(__name__)
app.secret_key = "black_final_v3"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")

print("=== BLACK DOWNLOADER STARTING ===")
print(f"Cookie exists? {os.path.exists(COOKIE_FILE)}")

TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Black Downloader</title>
<style>
body{font-family:Arial;background:#0a0a0a;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}
.box{background:#1a1a1a;padding:30px;border-radius:15px;width:90%;max-width:500px;box-shadow:0 0 20px #00ff88}
input{width:100%;padding:12px;border-radius:8px;border:none;margin:15px 0;box-sizing:border-box}
button{width:100%;padding:12px;background:#00ff88;color:#000;border:none;border-radius:8px;font-weight:bold;cursor:pointer}
#status{margin-top:15px;text-align:center}
a{color:#00ff88}
</style></head>
<body><div class="box">
<h2 style="text-align:center">Black Downloader 🔥</h2>
<input id="url" placeholder="Paste YouTube Shorts URL here...">
<button onclick="download()">Download</button>
<div id="status"></div>
</div>
<script>
let checkInterval;
function download(){
 let url=document.getElementById('url').value;
 if(!url){alert('Paste URL');return;}
 document.getElementById('status').innerHTML='⏳ Starting download... 0%';
 fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url})})
 .then(r=>r.json()).then(d=>{
   if(d.error){document.getElementById('status').innerHTML='❌ '+d.error; return;}
   checkInterval=setInterval(checkProgress,1000);
 });
}
function checkProgress(){
 fetch('/progress').then(r=>r.json()).then(d=>{
   if(d.status==='downloading'){
     document.getElementById('status').innerHTML='⏳ '+d.percent+' - '+d.speed;
   } else if(d.status==='finished'){
     clearInterval(checkInterval);
     document.getElementById('status').innerHTML='✅ Finished! <a href="/dl-file">Click to Save File</a>';
   } else if(d.status==='error'){
     clearInterval(checkInterval);
     document.getElementById('status').innerHTML='❌ '+d.error;
   }
 });
}
</script></body></html>
"""

def get_ydl_opts():
    opts = {
        'format': 'best[height<=720][ext=mp4]/best[height<=720]/best',
        'quiet': False,
        'no_warnings': False,
        'noplaylist': True,
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
        'extractor_args': {'youtube': {'player_client': ['android','ios','web']}},
        'retries': 3,
        'fragment_retries': 3,
    }
    if os.path.exists(COOKIE_FILE):
        print(f">>> USING COOKIE FILE: {COOKIE_FILE}")
        opts['cookiefile'] = COOKIE_FILE
    else:
        print(">>> NO COOKIE FILE")
    return opts

@app.route('/')
def home():
    return render_template_string(TEMPLATE)

@app.route('/download', methods=['POST'])
def dl():
    data = request.get_json()
    url = data.get('url','').strip()
    if not url:
        return jsonify({'error':'No URL'})
    session['progress'] = {'status':'downloading','percent':'0%','speed':''}
    
    def hook(d):
        if d['status']=='downloading':
            session['progress'] = {'status':'downloading','percent':d.get('_percent_str','0%'),'speed':d.get('_speed_str','')}
        elif d['status']=='finished':
            session['progress'] = {'status':'finished','file':d['filename']}
    
    try:
        opts = get_ydl_opts()
        opts['progress_hooks'] = [hook]
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            session['file'] = filename
            session['progress'] = {'status':'finished','file':filename}
            return jsonify({'success':True})
    except Exception as e:
        err = str(e)
        print(f"DOWNLOAD ERROR: {err}")
        session['progress'] = {'status':'error','error':err}
        return jsonify({'error':err})

@app.route('/progress')
def progress():
    return jsonify(session.get('progress', {'status':'idle'}))

@app.route('/dl-file')
def dl_file():
    f = session.get('file')
    if f and os.path.exists(f):
        return send_file(f, as_attachment=True)
    return "File not found, download again", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
