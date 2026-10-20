from flask import Flask, request, send_file
import requests, tempfile, os

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h3>Simple Downloader</h3>
    <input id='u' placeholder='Paste direct video link'>
    <button onclick='go()'>Go</button>
    <script>
    function go(){
      let u=document.getElementById('u').value;
      window.location='/dl?url='+encodeURIComponent(u)
    }
    </script>
    """

@app.route('/dl')
def dl():
    url = request.args.get('url')
    r = requests.get(url, stream=True, timeout=30)
    tmp = os.path.join(tempfile.gettempdir(), 'video.mp4')
    with open(tmp, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return send_file(tmp, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
