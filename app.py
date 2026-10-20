from flask import Flask, request, render_template_string, send_from_directory, redirect, jsonify
import os, sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== PUT YOUR ADSTERRA CODES HERE =====
POPUNDER = """<script type='text/javascript' src='//www.highperformanceformat.com/xxxx/invoke.js'></script>"""
SOCIAL_BAR = """<script type='text/javascript' src='//www.highperformanceformat.com/yyyy/invoke.js'></script>"""
DIRECT_LINK = "https://www.highperformanceformat.com/watch?key=YOUR_KEY"

online_users = {}

def init_db():
    conn = sqlite3.connect('visitors.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY, ip TEXT, page TEXT, date TEXT)''')
    conn.close()
init_db()

@app.before_request
def track():
    ip = request.remote_addr
    online_users[ip] = datetime.now()
    to_del = [k for k,v in online_users.items() if datetime.now() - v > timedelta(minutes=1)]
    for k in to_del: del online_users[k]
    try:
        if not request.path.startswith('/static') and not request.path.startswith('/api'):
            conn = sqlite3.connect('visitors.db')
            conn.execute("INSERT INTO visits (ip, page, date) VALUES (?, ?, ?)", (ip, request.path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
    except: pass

@app.route('/api/online')
def api_online():
    count = len(online_users)
    if count < 2: count = count + 1 # make am look busy
    return jsonify({"online": count})

BASE = """
<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FileShare - Earn</title>
""" + POPUNDER + """
<style>
body{font-family:Arial;background:#f5f5f5;padding:20px}
.box{background:white;padding:20px;border-radius:10px;max-width:600px;margin:auto;margin-top:50px}
.btn{display:block;background:#007bff;color:white;padding:15px;text-align:center;border-radius:8px;text-decoration:none;margin-top:10px;font-weight:bold}
#live{position:fixed;top:10px;right:10px;background:green;color:white;padding:8px 15px;border-radius:20px;font-weight:bold;z-index:9999}
.dot{height:10px;width:10px;background:#00ff00;border-radius:50%;display:inline-block;animation:blink 1s infinite}
@keyframes blink{0%{opacity:1}50%{opacity:0.2}}
</style>
<script>
let adOpened=false;
document.addEventListener('click', function(){
 if(!adOpened){ adOpened=true; window.open('""" + DIRECT_LINK + """','_blank'); }
});
function updateOnline(){
 fetch('/api/online').then(r=>r.json()).then(d=>{
  document.getElementById('num').innerText=d.online;
 });
}
setInterval(updateOnline,3000);
</script>
</head><body>
<div id="live"><span class="dot"></span> <span id="num">1</span> Online</div>
<div class="box">%s</div>
<div style="position:fixed;bottom:0;left:0;width:100%;text-align:center;z-index:999">""" + SOCIAL_BAR + """</div>
</body></html>
"""

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        f = request.files['file']
        if f: f.save(os.path.join(UPLOAD_FOLDER, f.filename))
        return redirect('/')
    files = os.listdir(UPLOAD_FOLDER)
    file_links = "".join([f"<a class=btn href='/download/{x}'>{x} - Download</a>" for x in files]) or "No files yet"
    content = f"<h2>📁 Fast File Share</h2><form method=post enctype=multipart/form-data><input type=file name=file required><button class=btn type=submit>Upload</button></form><hr>{file_links}<p style='text-align:center;margin-top:20px'><a href='/admin/stats'>📊 See Stats</a></p>"
    return render_template_string(BASE % content)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/admin/stats')
def stats():
    conn = sqlite3.connect('visitors.db')
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    unique = cur.execute("SELECT COUNT(DISTINCT ip) FROM visits").fetchone()[0]
    conn.close()
    return f"<h1>📊 Stats</h1><h2>Total Views: {total}</h2><h2>Unique Users: {unique}</h2><h2>Live Now: {len(online_users)}</h2><a href='/'>Back</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
