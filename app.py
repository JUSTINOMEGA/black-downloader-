from flask import Flask, render_template_string, request, jsonify, send_file, session
import yt_dlp, os, json, tempfile
from datetime import datetime

app = Flask(__name__)
app.secret_key = "black_working"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTER_FILE = os.path.join(BASE_DIR, "visitor_count.txt")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
VISITORS_FILE = os.path.join(BASE_DIR, "visitors_ips.json")

progress_data = {"percent": 0, "msg": "", "status": "idle"}

def get_count():
    if not os.path.exists(COUNTER_FILE):
        return 0
    try:
        with open(COUNTER_FILE,"r") as f:
            return int(f.read().strip() or 0)
    except:
        return 0

def get_ips():
    if not os.path.exists(VISITORS_FILE):
        return []
    try:
        with open(VISITORS_FILE,"r") as f:
            return json.load(f)
    except:
        return []

def get_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE,"r") as f:
            return json.load(f)
    except:
        return []

def add_count():
    if session.get('visited'):
        return get_count()
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
    ips = get_ips()
    if user_ip in ips:
        session['visited']=True
        return get_count()
    count = get_count()+1
    try:
        with open(COUNTER_FILE,"w") as f:
            f.write(str(count))
        ips.append(user_ip)
        with open(VISITORS_FILE,"w") as f:
            json.dump(ips[-2000:],f)
    except:
        pass
    session['visited']=True
    return count

def add_history(title,url):
    history=get_history()
    history.insert(0,{"title":title[:60],"url":url[:40],"time":datetime.now().strftime("%I:%M %p"),"date":datetime.now().strftime("%d %b")})
    history=history[:15]
    try:
        with open(HISTORY_FILE,"w") as f:
            json.dump(history,f)
    except:
        pass

def hook(d):
    global progress_data
    if d['status']=='downloading':
        try:
            pct=d.get('_percent_str','0%').strip()
            progress_data["msg"]=f"{pct} {d.get('_speed_str','')} ETA {d.get('_eta_str','')}"
            progress_data["percent"]=float(pct.replace('%',''))
        except:
            pass
    elif d['status']=='finished':
        progress_data["msg"]="Finalizing..."
        progress_data["percent"]=95

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
.input-icon{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:#555}
.paste-btn{background:#222;border:1px solid #333;color:#aaa;padding:0 14px;border-radius:12px;font-size:11px}
.options{display:flex;gap:8px;margin-top:14px}
.opt{flex:1;background:#0a0a0a;border:1.5px solid #252525;border-radius:10px;padding:12px;text-align:center;font-size:11px;cursor:pointer}
.opt.active{border-color:#ff0033;background:rgba(255,0,51,0.08)}
.btn-main{width:100%;margin-top:16px;background:linear-gradient(90deg,#ff0033,#ff4d00);border:none;padding:16px;border-radius:12px;color:#fff;font-weight:700;cursor:pointer}
.progress-sec{display:none;margin-top:16px;background:#0a0a0a;border:1px solid #222;border-radius:12px;padding:12px}
.progress-sec.show{display:block}
.p-bar{height:8px;background:#1a1a1a;border-radius:20px;overflow:hidden;margin-top:8px}
.p-fill{height:100%;width:0%;background:linear-gradient(90deg,#ff0033,#ff8a00)}
.history{margin-top:18px;background:#0f0f10;border:1px solid #1e1e1e;border-radius:16px;padding:16px}
.history h3{font-size:11px;color:#666;margin-bottom:10px}
.h-item{display:flex;justify-content:space-between;background:#161617;border:1px solid #222;padding:9px 12px;border-radius:8px;margin-bottom:6px;font-size:11px}
.platforms{display:flex;gap:10px;justify-content:center;margin:20px 0;flex-wrap:wrap}
.p-icon{width:58px;height:58px;border-radius:14px;display:flex;justify-content:center;align-items:center;font-size:26px;text-decoration:none;color:#fff;transition:0.2s;border:1.5px solid #222}
.p-icon:active{transform:scale(0.9)}
.p-icon.yt{background:#ff0000}
.p-icon.tk{background:#000;border-color:#333}
.p-icon.ig{background:linear-gradient(45deg,#feda75,#fa7e1e,#d62976,#962fbf,#4f5bd5)}
.p-icon.fb{background:#1877f2}
.p-icon.x{background:#000;border-color:#333}
.p-label{font-size:9px;text-align:center;color:#888;margin-top:4px}
.social-media{margin:18px 0;text-align:center;padding:18px;background:#0a0a0a;border-radius:16px;border:1px solid #1e1e1e}
.social-media a{border:2px solid #ff69b4 !important;border-radius:50%;width:44px;height:44px;display:inline-flex;justify-content:center;align-items:center;margin:5px;color:#ff69b4;background:#111;text-decoration:none;font-size:20px}
.platform-title{text-align:center;font-size:11px;color:#666;margin-top:18px;letter-spacing:1px}
</style>
<script data-cfasync="false" src="https://accountut.com/1/971d985f3a9db728c035958c5ca9625b"></script>
</head>
<body>
<div class="navbar"><div class="nav-logo">BLACK <span>DOWNLOADER</span></div><div style="color:#555;font-size:11px">{{count}} USERS</div></div>
<div class="hero"><div class="badge">LIVE {{count}} USERS</div><h1>DOWNLOAD <span>ANYTHING</span><br>IN 2 SECONDS</h1></div>
<div class="main">
<div class="stats"><div class="stat-box"><b>{{count}}</b>Users</div><div class="stat-box"><b>{{history|length}}</b>Today</div><div class="stat-box"><b>4.9</b>Rating</div></div>
<div class="card"><div class="inner">
<div class="input-box"><div class="input-icon"><i class="fas fa-link"></i></div><input id="urlInput" placeholder="Paste link..."><button class="paste-btn" onclick="navigator.clipboard.readText().then(t=>urlInput.value=t)">PASTE</button></div>
<div class="options"><div class="opt active" data-q="best"><b>BEST</b></div><div class="opt" data-q="worst"><b>FAST</b></div><div class="opt" data-q="audio"><b>MP3</b></div></div>
<button class="btn-main" id="dlBtn">DOWNLOAD TO MY PHONE</button>
<div class="progress-sec" id="progressSec"><div style="display:flex;justify-content:space-between;font-size:11px"><span id="pMsg">Starting...</span><span id="pPercent">0%</span></div><div class="p-bar"><div class="p-fill" id="pFill"></div></div></div>
</div></div>

<div class="platform-title">TAP TO OPEN PLATFORM & COPY LINK</div>
<div class="platforms">
<a href="https://www.youtube.com" target="_blank" class="p-icon yt"><i class="fab fa-youtube"></i></a>
<a href="https://www.tiktok.com" target="_blank" class="p-icon tk"><i class="fab fa-tiktok"></i></a>
<a href="https://www.instagram.com" target="_blank" class="p-icon ig"><i class="fab fa-instagram"></i></a>
<a href="https://www.facebook.com" target="_blank" class="p-icon fb"><i class="fab fa-facebook-f"></i></a>
<a href="https://www.x.com" target="_blank" class="p-icon x"><i class="fab fa-x-twitter"></i></a>
</div>

<div class="history"><h3>RECENT</h3>
{% for h in history %}<div class="h-item"><div>{{h.title}}</div><span>{{h.date}}</span></div>{% else %}<div class="h-item"><div style="color:#555">No downloads yet</div></div>{% endfor %}
</div>
<div class="social-media"><a href="#"><i class="fab fa-facebook-f"></i></a><a href="#"><i class="fab fa-whatsapp"></i></a><a href="#"><i class="fab fa-tiktok"></i></a><a href="#"><i class="fab fa-instagram"></i></a><a href="#"><i class="fab fa-youtube"></i></a></div>
</div>
<script>
let quality="best";
document.querySelectorAll('.opt').forEach(o=>{
 o.onclick=()=>{
  document.querySelectorAll('.opt').forEach(x=>x.classList.remove('active'));
  o.classList.add('active');
  quality=o.dataset.q;
 }
});
const urlInput=document.getElementById('urlInput');
const dlBtn=document.getElementById('dlBtn');
const progressSec=document.getElementById('progressSec');
const pFill=document.getElementById('pFill');
const pPercent=document.getElementById('pPercent');
const pMsg=document.getElementById('pMsg');
dlBtn.onclick=async()=>{
 const url=urlInput.value.trim();
 if(!url) return alert('Paste link');
 dlBtn.disabled=true;
 dlBtn.innerText='STARTING...';
 progressSec.classList.add('show');
 let interval=setInterval(async()=>{
  try{
   let r=await fetch('/progress');
   let d=await r.json();
   pFill.style.width=d.percent+'%';
   pPercent.innerText=Math.round(d.percent)+'%';
   pMsg.innerText=d.msg;
  }catch(e){}
 },800);
 try{
  let res=await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,quality})});
  clearInterval(interval);
  if(res.headers.get('content-disposition')){
   let blob=await res.blob();
   let fn=res.headers.get('content-disposition').split('filename=')[1]||'video.mp4';
   fn=fn.replace(/"/g,'');
   let a=document.createElement('a');
   a.href=URL.createObjectURL(blob);
   a.download=fn;
   document.body.appendChild(a);
   a.click();
   a.remove();
   pFill.style.width='100%';
   pPercent.innerText='100%';
   pMsg.innerText='Saved!';
   setTimeout(()=>location.reload(),2000);
  } else {
   let data=await res.json();
   if(!data.success){
    alert(data.error);
    progressSec.classList.remove('show');
   }
  }
 }catch(e){
  clearInterval(interval);
  alert('Error:'+e);
  progressSec.classList.remove('show');
 }
 dlBtn.disabled=false;
 dlBtn.innerText='DOWNLOAD TO MY PHONE';
}
</script>
<script data-cfasync="false" src="https://bellnewyork.org/14/8f7482c247ef50d1caa5cf7d56f6c1e6"></script>
</body></html>
"""

@app.route('/')
def home():
    count = add_count()
    history = get_history()
    return render_template_string(HTML, count=count, history=history)

@app.route('/progress')
def progress():
    return jsonify(progress_data)

@app.route('/download', methods=['POST'])
def download():
    global progress_data
    data = request.json
    url = data.get('url')
    q = data.get('quality','best')
    progress_data = {"percent": 0, "msg": "Starting...", "status": "downloading"}
    temp_dir = tempfile.mkdtemp()
    try:
        if q == 'audio':
            opts = {'format':'bestaudio/best','outtmpl':f'{temp_dir}/%(title)s.%(ext)s','progress_hooks':[hook],'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]}
        elif q == 'worst':
            opts = {'format':'worst','outtmpl':f'{temp_dir}/%(title)s.%(ext)s','progress_hooks':[hook]}
        else:
            opts = {'format':'best[ext=mp4]/best','outtmpl':f'{temp_dir}/%(title)s.%(ext)s','progress_hooks':[hook]}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title','Video')
        files = os.listdir(temp_dir)
        if files:
            file_path = os.path.join(temp_dir, files[0])
            progress_data = {"percent": 100, "msg": "Sending...", "status": "done"}
            add_history(title, url)
            return send_file(file_path, as_attachment=True, download_name=files[0])
        return jsonify({"success": True})
    except Exception as e:
        progress_data = {"percent": 0, "msg": f"Error: {str(e)}", "status": "error"}
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
