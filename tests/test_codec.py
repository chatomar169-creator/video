import os, tempfile, unittest, subprocess
from pathlib import Path
from codec import encode, decode

class Roundtrip(unittest.TestCase):
    def test_roundtrip_and_transcode(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'out').mkdir()
            for name,data in [('random.bin',os.urandom(12000)),('empty.bin',b''),('text.txt',b'hello'*10000)]:
                source=p/name; source.write_bytes(data)
                encode(source,p/'video.mp4')
                self.assertEqual(decode(p/'video.mp4',p/'out').read_bytes(),data)
            source=p/'random.bin'
            encode(source,p/'4k.mp4',True)
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(p/'4k.mp4'),'-vf','scale=1920:1080','-c:v','libx264','-crf','23',str(p/'compressed.mp4')],check=True)
            self.assertEqual(decode(p/'compressed.mp4',p/'out').read_bytes(),source.read_bytes())
    def test_invalid_video(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/'bad.mp4').write_bytes(b'bad')
            with self.assertRaises(ValueError): decode(p/'bad.mp4',p)

if __name__=='__main__': unittest.main()
