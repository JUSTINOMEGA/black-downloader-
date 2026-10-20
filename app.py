from flask import Flask, request, render_template_string, send_from_directory, redirect
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== ADSTERRA CODES - PUT YOUR OWN HERE =====
POPUNDER_CODE = """<script type='text/javascript' src='//www.highperformanceformat.com/xxxxxx/invoke.js'></script>"""
SOCIAL_BAR_CODE = """<script type='text/javascript' src='//www.highperformanceformat.com/yyyyyy/invoke.js'></script>"""
DIRECT_LINK = "https://www.highperformanceformat.com/watch?key=YOUR_KEY"

# ===== VISITOR TRACKER =====
def init_db():
    conn = sqlite3.connect('visitors.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS visits
                 (id INTEGER PRIMARY KEY, ip TEXT, page TEXT, date TEXT, user_agent TEXT)''')
    conn.close()

init_db()

@app.before_request
def track():
    if request.path.startswith('/static') or request.path.startswith('/admin'):
        return
    try:
        conn = sqlite3.connect('visitors.db')
        conn.execute("INSERT INTO visits (ip, page, date, user_agent) VALUES (?, ?, ?, ?)",
                     (request.remote_addr, request.path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request.headers.get('User-Agent','')))
        conn.commit()
        conn.close()
    except:
        pass

BASE_HTML = """
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FileShare - Fast Download</title>
{{POPUNDER}}
<style>
body{font-family:Arial;background:#f5f5f5;padding:20px}
.box{background:white;padding:20px;border-radius:10px;max-width:600px;margin:auto}
a.btn{display:block;background:#007bff;color:white;padding:15px;text-align:center;border-radius:8px;text-decoration:none;margin-top:10px;font-weight:bold}
#ad-sticky{position:fixed;bottom:0;left:0;width:100%;background:#111;color:#fff;padding:10px;text-align:center;z-index:9999}
</style>
<script>
// Make money even if user leaves - open ad on first click
let adOpened = false;
document.addEventListener('click', function(){
    if(!adOpened){
        adOpened = true;
        window.open('{{DIRECT}}', '_blank');
    }
});
</script>
</head>
<body>
<div class="box">
<h2>📁 Fast File Share</h2>
%s
</div>

<div id="ad-sticky">
{{SOCIAL}}
</div>
</body>
</html>
""" % "%%s"

INDEX_CONTENT = """
<form method=post enctype=multipart/form-data>
<input type=file name=file required>
<button class="btn" type=submit>Upload File</button>
</form>
<hr>
<h3>Files:</h3>
%s
"""

@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        f = request.files['file']
        if f:
            f.save(os.path.join(UPLOAD_FOLDER, f.filename))
            return redirect('/')
    
    files = os.listdir(UPLOAD_FOLDER)
    file_links = "".join([f"<a class='btn' href='/download/{x}'>{x} - Download</a>" for x in files]) or "No files yet"
    content = INDEX_CONTENT % file_links
    html = BASE_HTML % content
    html = html.replace('{{POPUNDER}}', POPUNDER_CODE).replace('{{SOCIAL}}', SOCIAL_BAR_CODE).replace('{{DIRECT}}', DIRECT_LINK)
    return render_template_string(html)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/admin/stats')
def stats():
    conn = sqlite3.connect('visitors.db')
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    today_str = datetime.now().strftime("%Y-%m-%d")
    today = cur.execute("SELECT COUNT(*) FROM visits WHERE date LIKE ?", (f"{today_str}%",)).fetchone()[0]
    unique = cur.execute("SELECT COUNT(DISTINCT ip) FROM visits").fetchone()[0]
    pages = cur.execute("SELECT page, COUNT(*) as c FROM visits GROUP BY page ORDER BY c DESC LIMIT 10").fetchall()
    conn.close()
    
    pages_html = "".join([f"<tr><td>{p[0]}</td><td>{p[1]}</td></tr>" for p in pages])
    return f"""
    <h1>📊 Your Website Stats</h1>
    <h2>Total Views: {total}</h2>
    <h2>Today: {today}</h2>
    <h2>Unique Users (IPs): {unique}</h2>
    <hr>
    <table border=1 cellpadding=10><tr><th>Page</th><th>Views</th></tr>{pages_html}</table>
    <p>Check this page everyday to know how many people use your site.</p>
    <a href='/'>Back to Home</a>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
