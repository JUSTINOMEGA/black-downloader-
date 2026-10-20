from flask import Flask, render_template_string, request, jsonify, send_file, session
import yt_dlp, os, json, tempfile
from datetime import datetime

app = Flask(__name__)
app.secret_key = "black_render_working"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTER_FILE = os.path.join(BASE_DIR, "visitor_count.txt")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
VISITORS_FILE = os.path.join(BASE_DIR, "visitors_ips.json")

progress_data = {"percent": 0, "msg": "", "status": "idle"}

def get_count():
    if not os.path.exists(COUNTER_FILE): return 0
    try:
        with open(COUNTER_FILE,"r") as f: return int(f.read().strip() or 0)
    except: return 0

def get_ips():
    if not os.path.exists(VISITORS_FILE): return []
    try:
        with open(VISITORS_FILE,"r") as f: return json.load(f)
    except: return []

def get_history():
    if not os.path.exists(HISTORY_FILE): return []
    try:
        with open(HISTORY_FILE,"r") as f: return json.load(f)
    except: return []

def add_count():
    if session.get('visited'): return get_count()
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
    ips = get_ips()
    if user_ip in ips:
        session['visited']=True
        return get_count()
    count = get_count()+1
    try:
        with open(COUNTER_FILE,"w") as f: f.write(str(count))
        ips.append(user_ip)
        with open(VISITORS_FILE,"w") as f: json.dump(ips[-2000:],f)
    except: pass
    session['visited']=True
    return count

def add_history(title,url):
    history=get_history()
    history.insert(0,{"title":title[:60],"url":url[:40],"time":datetime.now().strftime("%I:%M %p"),"date":datetime.now().strftime("%d %b")})
    history=history[:15]
    try:
        with open(HISTORY_FILE,"w") as f: json.dump(history,f)
    except: pass

def hook(d):
    global progress_data
    if d['status']=='downloading':
        try:
            pct=d.get('_percent_str','0%').strip()
            progress_data["msg"]=f"{pct} {d.get('_speed_str','')} ETA {d.get('_eta_str','')}"
            progress_data["percent"]=float(pct.replace('%',''))
        except: pass
    elif d['status']=='finished':
        progress_data["msg"]="Finalizing..."
        progress_data["percent"]=95

# ===== FIXED YDL OPTIONS TO BYPASS BOT ERROR =====
def get_ydl_opts():
    return {
        'format': 'best[height<=720]/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'progress_hooks': [hook],
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'player_skip': ['webpage', 'configs', 'js'],
                'skip': ['hls', 'dash']
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; en_US) gzip',
        }
    }

HTML = """ YOUR FULL HTML HERE - KEEP YOUR OLD HTML """

# Copy your old HTML from line 85 downwards and keep it here
# To make it easy, I will use simple HTML, you can keep your old design
# PASTE YOUR OLD HTML VARIABLE COMPLETELY IF THIS ONE OVERRIDE DESIGN

HTML = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BLACK Downloader</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:Inter}
body{background:#050507;color:#fff;min-height:100vh}
.navbar{display:flex;justify-content:space-between;padding:18px 22px;border-bottom:1px solid #1a1a1a}
.nav-logo{font-weight:800;font-size:22px}
.nav-logo span{color:#ff0033}
.hero{text-align:center;padding:35px 20px 10px}
.badge{background:#161616;border:1px solid #2a2a2a;padding:6px 14px;border-radius:20px;font-size:11px;color:#00ff88;display:inline-block;margin-bottom:14px}
.hero h1{font-size:48px;font-weight:800;line-height:0.95}
.hero h1 span{color:#ff0033}
.main{max-width:700px;margin:0 auto;padding:0 15px}
.stats{display:flex;gap:8px;justify-content:center;margin:16px 0}
.stat-box{background:#111;border:1px solid #222;padding:12px 18px;border-radius:12px;font-size:11px;text-align:center;min-width:100px}
.stat-box b{color:#ff69b4;font-size:19px;display:block}
.card{background:#0f0f10;border:1px solid #1e1e1e;border-radius:20px;padding:6px}
.inner{background:#161617;border-radius:16px;padding:22px}
.input-box{display:flex;gap:8px;position:relative}
.input-box input{flex:1;background:#0a0a0a;border:1.5px solid #252525;border-radius:12px;padding:16px 14px 16px 42px;color:#fff;outline:none}
.input-box i{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:#555}
.btn{background:#ff0033;color:#fff;border:none;padding:16px 22px;border-radius:12px;font-weight:700;cursor:pointer}
.progress{margin-top:15px;background:#0a0a0a;border-radius:10px;height:8px;overflow:hidden;display:none}
.progress-bar{height:100%;background:#ff0033;width:0%;transition:.3s}
#status{margin-top:10px;font-size:12px;color:#888}
</style></head><body>
<div class="navbar"><div class="nav-logo">BLACK <span>DOWNLOADER</span></div></div>
<div class="hero"><div class="badge"><i class="fa-solid fa-circle" style="color:#00ff88;font-size:6px"></i> LIVE</div>
<h1>DOWNLOAD <br><span>ANYTHING</span></h1></div>
<div class="main">
<div class="stats"><div class="stat-box"><b>{{count}}</b>VISITORS</div><div class="stat-box"><b>100%</b>FAST</div><div class="stat-box"><b>HD</b>QUALITY</div></div>
<div class="card"><div class="inner">
<div class="input-box"><i class="fa-solid fa-link"></i><input id="url" placeholder="Paste YouTube, TikTok, IG link..."><button class="btn" onclick="getInfo()">GO</button></div>
<div class="progress" id="prog"><div class="progress-bar" id="bar"></div></div>
<div id="status"></div>
<div id="result" style="margin-top:15px"></div>
</div></div></div>
<script>
async function getInfo(){
  let u=document.getElementById('url').value;
  if(!u) return alert('Paste link!');
  document.getElementById('status').innerText='Checking...';
  document.getElementById('prog').style.display='block';
  let r=await fetch('/info',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:u})});
  let d=await r.json();
  if(d.error){document.getElementById('status').innerText=d.error;return}
  document.getElementById('status').innerText=d.title;
  document.getElementById('result').innerHTML=`<button class="btn" style="width:100%" onclick="download('${u}')">DOWNLOAD NOW <i class="fa-solid fa-download"></i></button>`;
}
async function download(u){
  document.getElementById('status').innerText='Downloading...';
  window.location='/download?url='+encodeURIComponent(u);
}
setInterval(async()=>{
  let r=await fetch('/progress');let d=await r.json();
  document.getElementById('bar').style.width=d.percent+'%';
  if(d.msg) document.getElementById('status').innerText=d.msg;
},800);
</script></body></html>
"""

@app.route('/')
def home():
    count = add_count()
    history = get_history()
    return render_template_string(HTML, count=count, history=history)

@app.route('/info', methods=['POST'])
def info():
    global progress_data
    progress_data = {"percent": 0, "msg": "", "status": "idle"}
    data = request.get_json()
    url = data.get('url','').strip()
    if not url: return jsonify({"error": "No URL"})
    try:
        ydl_opts = get_ydl_opts()
        # For info we don't need hook
        ydl_opts.pop('progress_hooks', None)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title','Video')
            add_history(title, url)
            return jsonify({"title": title})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/download')
def download():
    global progress_data
    progress_data = {"percent": 0, "msg": "Starting...", "status": "downloading"}
    url = request.args.get('url','')
    if not url: return "No URL", 400
    try:
        tmp = tempfile.mkdtemp()
        ydl_opts = get_ydl_opts()
        ydl_opts['outtmpl'] = os.path.join(tmp, '%(title)s.%(ext)s')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        progress_data = {"percent": 100, "msg": "Done!", "status": "finished"}
        return send_file(filename, as_attachment=True)
    except Exception as e:
        progress_data = {"percent": 0, "msg": f"Error: {e}", "status": "error"}
        return f"Error: {e}", 500

@app.route('/progress')
def progress():
    return jsonify(progress_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
