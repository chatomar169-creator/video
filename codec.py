"""Fixed-grid optical file transport; version 1, 1080p/30fps."""
import hashlib, json, math, struct, subprocess, tempfile, zlib
from pathlib import Path
import numpy as np

W, H, CELL, FPS = 1920, 1080, 8, 30
COLS, ROWS = W // CELL, H // CELL
BYTES = COLS * ROWS // 24  # three spatial copies of each bit
HEADER = struct.Struct('>4sIII')
PAYLOAD = BYTES - HEADER.size
LIMIT = 20 * 1024 * 1024


def run(args, **kw):
    return subprocess.run(args, check=True, stderr=subprocess.PIPE, **kw)


def encode(source, destination, upscale=False):
    source, destination = Path(source), Path(destination)
    data = source.read_bytes()
    if len(data) > LIMIT:
        raise ValueError('Maximum input size is 20 MiB')
    compressed = zlib.compress(data, 9)
    use_zip = len(compressed) < len(data)
    meta = json.dumps({'name': source.name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'compressed': use_zip}).encode()
    body = struct.pack('>I', len(meta)) + meta + (compressed if use_zip else data)
    body = struct.pack('>Q', len(body)) + body
    total = math.ceil(len(body) / PAYLOAD)
    args = ['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','gray','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an']
    if upscale:
        args += ['-vf','scale=3840:2160:flags=neighbor']
    args += ['-c:v','libx264','-preset','fast','-crf','12','-pix_fmt','yuv420p',str(destination)]
    with tempfile.TemporaryFile() as errors:
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=errors)
        try:
            for i in range(total):
                payload = body[i*PAYLOAD:(i+1)*PAYLOAD].ljust(PAYLOAD,b'\0')
                packet = HEADER.pack(b'BV01',i,total,zlib.crc32(payload)) + payload
                bits = np.tile(np.unpackbits(np.frombuffer(packet,dtype=np.uint8)),3)
                grid = np.zeros(ROWS*COLS,dtype=np.uint8)
                grid[:len(bits)] = bits * 255
                frame = np.repeat(np.repeat(grid.reshape(ROWS,COLS),CELL,0),CELL,1)
                p.stdin.write(frame.tobytes())
            p.stdin.close()
            if p.wait():
                errors.seek(0)
                raise ValueError(errors.read().decode())
        finally:
            if p.poll() is None:
                p.kill(); p.wait()
    return {'frames':total,'seconds':total/FPS,'original_bytes':len(data),'video_bytes':destination.stat().st_size}


def decode(video, output_dir):
    packets = {}; expected = None
    with tempfile.TemporaryFile() as errors:
        p = subprocess.Popen(['ffmpeg','-v','error','-i',str(video),'-vf',f'scale={W}:{H}:flags=area','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE,stderr=errors)
        try:
            while True:
                raw = p.stdout.read(W*H)
                if not raw: break
                if len(raw) != W*H: raise ValueError('Truncated frame')
                a = np.frombuffer(raw,dtype=np.uint8).reshape(ROWS,CELL,COLS,CELL)
                samples = a[:,2:6,:,2:6].mean(axis=(1,3)).ravel()
                copies = (samples[:BYTES*24] > 127).reshape(3,-1)
                packet = np.packbits(copies.sum(axis=0)>=2).tobytes()
                magic, index, total, crc = HEADER.unpack(packet[:HEADER.size])
                payload = packet[HEADER.size:]
                if magic != b'BV01' or zlib.crc32(payload) != crc: continue
                if not 0 <= index < total <= math.ceil((LIMIT+8192)/PAYLOAD): continue
                if expected is not None and expected != total: raise ValueError('Mixed videos')
                expected = total; packets[index] = payload
            if p.wait(): raise ValueError('Video decoding failed')
        finally:
            p.stdout.close()
            if p.poll() is None: p.kill(); p.wait()
    if expected is None or len(packets)!=expected:
        raise ValueError(f'Incomplete data: recovered {len(packets)} of {expected or "unknown"} frames')
    body = b''.join(packets[i] for i in range(expected))
    length = struct.unpack('>Q',body[:8])[0]
    if length > len(body)-8: raise ValueError('Invalid length')
    body = body[8:8+length]
    n = struct.unpack('>I',body[:4])[0]
    if n > 4096: raise ValueError('Invalid metadata')
    meta = json.loads(body[4:4+n]); data = body[4+n:]
    if meta['compressed']:
        dec = zlib.decompressobj(); data = dec.decompress(data,LIMIT+1)
        if not dec.eof or dec.unused_data: raise ValueError('Invalid compressed payload')
    if len(data)>LIMIT or len(data)!=meta['size'] or hashlib.sha256(data).hexdigest()!=meta['sha256']:
        raise ValueError('File integrity check failed')
    name = Path(meta['name']).name
    if name in ('','.','..'): raise ValueError('Invalid filename')
    output = Path(output_dir)/name
    output.write_bytes(data)
    return output
