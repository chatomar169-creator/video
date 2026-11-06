# Binary Video — cloud prototype

Convert arbitrary files into black/white 1080p 30fps MP4 videos and recover the original bytes with SHA-256 verification. Optional nearest-neighbor 4K export does not increase capacity. Runs on the cloud server, not the user's computer.

## Google Colab (no local installation)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/chatomar169-creator/video/blob/main/notebooks/Binary_Video_Colab.ipynb)

Open the notebook, connect to a CPU runtime, run setup, then run either the encode or decode cell. Arabic instructions and upload/download buttons are included. Processing happens in Colab; no web server or port forwarding is needed. Download results before the temporary session ends. YouTube upload is not included.

## Run

Run these commands on your **cloud Linux server** (Python 3.12+ required):

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg python3-venv git
git clone https://github.com/chatomar169-creator/video.git
cd video
./setup.sh
./start.sh
```

`setup.sh` creates an isolated virtual environment, installs the pinned dependency and runs the tests. `start.sh` starts the web interface. For an existing checkout, run the last two commands from its directory. No software installation on your personal computer is needed.

The HTTP service binds to 127.0.0.1:8080. Use an authenticated cloud gateway for remote access; this prototype intentionally has no public deployment or account authentication. Do not expose it directly to the Internet.

## Format and limits

Version BV01: 8px cells, 240×135 grid, three spatial copies per bit with majority voting, indexed frames, per-frame CRC32, optional zlib compression, SHA-256 of original bytes. Useful frame payload: 1334 bytes, about 40 KB/s before metadata. About 8.7 minutes per 20 MiB of incompressible data. Every frame is required: no frame-erasure correction yet. Fixed full-frame geometry; cropping and rotation are unsupported. Bad or incomplete data is rejected. YouTube recompression is NOT verified and automatic YouTube upload is not implemented.

Input limit 20 MiB; video upload limit 256 MiB. One conversion at a time. Files are stored in /tmp/binary-video (override VIDEO_DATA_DIR); delete job directories when no longer needed. Processes do not survive cloud snapshots: restart app.py in each session. Use the existing checkout; do not create worktrees unless requested.

Tests exercise random, compressible and empty files, invalid-video rejection, and 4K encoding followed by 1080p H.264 CRF23 transcoding. Local transcoding is not a substitute for a real YouTube test.

Next steps: frame-erasure correction, geometry markers, measured codec profiles, asynchronous durable jobs, authenticated hosting and YouTube OAuth integration. Never discard original files based on this experimental transport.
