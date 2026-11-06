import json, os, tempfile, threading, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote
from codec import encode, decode, LIMIT

ROOT = Path(os.environ.get('VIDEO_DATA_DIR','/tmp/binary-video'))
ROOT.mkdir(parents=True,exist_ok=True)
LOCK = threading.Lock()
PAGE = '''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>ملف ↔ فيديو</title><style>body{background:#101827;color:#eef;font:18px system-ui;max-width:760px;margin:60px auto;padding:24px}button,input,select{padding:12px;margin:12px 0}a{color:#8df}pre{white-space:pre-wrap}</style><h1>ملف ↔ فيديو</h1><p>المعالجة تتم داخل الخادم السحابي. حد الملف 20 MiB. الفيديو 1080p و30 إطارًا/ثانية مع تكرار البتات ثلاث مرات.</p><p>نسخة تجريبية: تحمّل ضغط يوتيوب غير مُثبت، والرفع التلقائي غير مفعّل. احتفظ بالملف الأصلي.</p><input type="file" id="file"><br><select id="mode"><option value="encode">ملف إلى فيديو</option><option value="decode">فيديو إلى ملف</option></select><label><input type="checkbox" id="four"> إخراج 4K (لا يزيد سعة البيانات)</label><br><button id="go">ابدأ</button><p id="estimate"></p><pre id="status"></pre><a id="result"></a><script>
file.onchange=()=>estimate.textContent=file.files[0]?'مدة تقريبية قبل الضغط: '+Math.ceil((file.files[0].size+256)/1334/30)+' ثانية':'';
go.onclick=async()=>{if(!file.files[0])return;go.disabled=true;document.getElementById('status').textContent='جارٍ العمل على الخادم…';result.textContent='';try{let r=await fetch('/api/'+mode.value+'?name='+encodeURIComponent(file.files[0].name)+'&four='+four.checked,{method:'POST',body:file.files[0]});let d=await r.json();if(!r.ok)throw Error(d.error);document.getElementById('status').textContent=JSON.stringify(d.stats||{verified:true},null,2);result.href=d.url;result.textContent='تنزيل النتيجة';}catch(e){document.getElementById('status').textContent=e.message}finally{go.disabled=false}};
</script></html>'''

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data, kind='application/json'):
        data = data.encode() if isinstance(data,str) else data
        self.send_response(code); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/': return self.reply(200,PAGE,'text/html; charset=utf-8')
        parts = path.split('/')
        if len(parts)==3 and parts[1]=='download' and len(parts[2])==32 and all(c in '0123456789abcdef' for c in parts[2]):
            folder=ROOT/parts[2]; info=folder/'result.json'
            if info.exists():
                name=json.loads(info.read_text())['name']; data=(folder/'output'/name).read_bytes()
                self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Length',str(len(data))); self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(name)); self.end_headers(); self.wfile.write(data); return
        self.reply(404,'{}')
    def do_POST(self):
        parsed=urlparse(self.path)
        if parsed.path not in ('/api/encode','/api/decode'): return self.reply(404,'{}')
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError: return self.reply(400,'{"error":"Invalid length"}')
        maximum=LIMIT if parsed.path.endswith('encode') else 256*1024*1024
        if not 0<size<=maximum: return self.reply(413,'{"error":"Upload exceeds limit or is empty"}')
        if not LOCK.acquire(False): return self.reply(429,'{"error":"Server busy"}')
        try:
            ident=uuid.uuid4().hex; folder=ROOT/ident; folder.mkdir(); (folder/'output').mkdir()
            q=parse_qs(parsed.query); name=Path(q.get('name',['input.bin'])[0]).name
            if name in ('','.','..'): raise ValueError('Invalid name')
            source=folder/name
            with source.open('wb') as f:
                remaining=size
                while remaining:
                    block=self.rfile.read(min(1024*1024,remaining))
                    if not block: raise ValueError('Incomplete upload')
                    f.write(block); remaining-=len(block)
            if parsed.path.endswith('encode'):
                output=folder/'output'/'encoded.mp4'; stats=encode(source,output,q.get('four')==['true'])
            else: output=decode(source,folder/'output'); stats={'sha256_verified':True}
            (folder/'result.json').write_text(json.dumps({'name':output.name}))
            self.reply(200,json.dumps({'url':'/download/'+ident,'stats':stats}))
        except Exception as e: self.reply(400,json.dumps({'error':str(e)}))
        finally: LOCK.release()

if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',8080),Handler).serve_forever()
