from flask import Flask, request, render_template_string, send_from_directory, redirect, jsonify
import os, sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

online_users = {}

def init_db():
    conn = sqlite3.connect('visitors.db')
    conn.execute('CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY, ip TEXT, page TEXT, date TEXT)')
    conn.close()
init_db()

@app.before_request
def track():
    ip = request.remote_addr
    online_users[ip] = datetime.now()
    for k in list(online_users.keys()):
        if datetime.now() - online_users[k] > timedelta(minutes=1):
            del online_users[k]

@app.route('/api/online')
def api_online():
    count = len(online_users)
    if count < 2:
        count = count + 1
    return jsonify({"online": count})

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        f = request.files['file']
        if f:
            f.save(os.path.join(UPLOAD_FOLDER, f.filename))
        return redirect('/')
    
    files = os.listdir(UPLOAD_FOLDER)
    links = ""
    for x in files:
        links += f"<a class=btn href='/download/{x}'>{x} - Download</a>"
    if not links:
        links = "No files yet"

    html = """
    <!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>FileShare</title>
    <style>
    body{font-family:Arial;background:#f5f5f5;padding:20px}
    .box{background:white;padding:20px;border-radius:10px;max-width:600px;margin:auto;margin-top:60px}
    .btn{display:block;background:#007bff;color:white;padding:15px;text-align:center;border-radius:8px;text-decoration:none;margin-top:10px;font-weight:bold}
    #live{position:fixed;top:10px;right:10px;background:green;color:white;padding:8px 15px;border-radius:20px;font-weight:bold;z-index:9999}
    .dot{height:10px;width:10px;background:#0f0;border-radius:50%;display:inline-block;animation:blink 1s infinite}
    @keyframes blink{0%{opacity:1}50%{opacity:0.2}}
    </style>
    <!-- YOUR ADS - THEY NO GO BREAK AGAIN -->
    <script data-cfasync="false" src="https://accountut.com/1/87e172de6eacde98194e479419b0040d"></script>
    <script data-cfasync="false" src="https://bellnewyork.org/14/ec5cf818a8aaeaa6ab2ab10d72065ce4"></script>
    </head><body>
    <div id="live"><span class="dot"></span> <span id="num">1</span> Online</div>
    <div class="box"><h2>📁 FileShare</h2>
    <form method=post enctype=multipart/form-data><input type=file name=file required><button class=btn type=submit>Upload</button></form><hr>
    """ + links + """
    <p style="text-align:center"><a href='/admin/stats'>📊 See Stats</a></p></div>
    <script>
    function upd(){fetch('/api/online').then(r=>r.json()).then(d=>{document.getElementById('num').innerText=d.online;});}
    setInterval(upd,3000); upd();
    </script>
    </body></html>
    """
    return render_template_string(html)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/admin/stats')
def stats():
    conn = sqlite3.connect('visitors.db')
    total = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    unique = conn.execute("SELECT COUNT(DISTINCT ip) FROM visits").fetchone()[0]
    conn.close()
    return f"<h1>Stats</h1>Total Views: {total}<br>Unique: {unique}<br>Live Now: {len(online_users)}<br><br><a href='/'>Home</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
