from flask import Flask, request, render_template_string, send_from_directory, redirect, jsonify
import os, sqlite3, json
from datetime import datetime, timedelta

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- TRACK ONLINE USERS ---
online_users = {} # ip : last_seen_time

def init_db():
    conn = sqlite3.connect('visitors.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS visits
                 (id INTEGER PRIMARY KEY, ip TEXT, page TEXT, date TEXT)''')
    conn.close()
init_db()

@app.before_request
def track():
    ip = request.remote_addr
    online_users[ip] = datetime.now() # update last seen
    # clean old offline (more than 1 min)
    to_del = [k for k,v in online_users.items() if datetime.now() - v > timedelta(minutes=1)]
    for k in to_del: del online_users[k]

@app.route('/api/online')
def api_online():
    count = len(online_users)
    # make am look busy even if na 1 person - add small random
    if count < 2: count = count + 1 
    return jsonify({"online": count})

BASE_HTML = """
<!doctype html>
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FileShare</title>
<style>
body{font-family:Arial;background:#f5f5f5;padding:20px}
.box{background:white;padding:20px;border-radius:10px;max-width:600px;margin:auto}
.btn{display:block;background:#007bff;color:white;padding:15px;text-align:center;border-radius:8px;text-decoration:none;margin-top:10px;font-weight:bold}
#live{position:fixed;top:10px;right:10px;background:green;color:white;padding:8px 15px;border-radius:20px;font-weight:bold;z-index:9999}
.dot{height:10px;width:10px;background:#00ff00;border-radius:50%;display:inline-block;animation:blink 1s infinite}
@keyframes blink{0%{opacity:1}50%{opacity:0.2}}
</style>
</head>
<body>
<div id="live"><span class="dot"></span> <span id="num">1</span> Online</div>
<div class="box"><h2>📁 Fast File Share</h2>%s</div>
<script>
function updateOnline(){
 fetch('/api/online').then(r=>r.json()).then(d=>{
   document.getElementById('num').innerText = d.online;
 });
}
setInterval(updateOnline, 3000); // update every 3 sec LIVE
updateOnline();
</script>
</body>
</html>
"""

INDEX_CONTENT = """
<form method=post enctype=multipart/form-data>
<input type=file name=file required>
<button class=btn type=submit>Upload</button>
</form><hr>%s
"""

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        f = request.files['file']
        if f: f.save(os.path.join(UPLOAD_FOLDER, f.filename))
        return redirect('/')
    files = os.listdir(UPLOAD_FOLDER)
    file_links = "".join([f"<a class=btn href='/download/{x}'>{x}</a>" for x in files]) or "No files"
    content = INDEX_CONTENT % file_links
    return render_template_string(BASE_HTML % content)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/admin/stats')
def stats():
    conn = sqlite3.connect('visitors.db')
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    conn.close()
    return f"Total: {total} | Live Now: {len(online_users)} | <a href='/'>Home</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
