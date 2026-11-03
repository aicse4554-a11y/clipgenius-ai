# ClipGenius AI — local-first MVP

A real, local-first video clipping application. The MVP supports video upload, metadata inspection,
speech transcription (Faster-Whisper), transcript-based highlight suggestions, FFmpeg clip rendering,
and downloadable MP4/SRT outputs. No billing, subscriptions, watermarking, or paid feature gates.

## Requirements
- Python 3.10+
- Node.js 20+
- FFmpeg + FFprobe installed and available on PATH
- 8 GB RAM recommended; a GPU is optional
- Faster-Whisper model downloads on first use (choose a smaller model for low-resource machines)

## Run the backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000/docs to inspect the API.

## Run the frontend
In another terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000.

## First run
1. Upload an MP4, MOV, WEBM, or MKV.
2. Choose a target clip duration and click **Find highlights**.
3. The backend probes the file, transcribes speech, ranks candidate windows, and renders clips.
4. Download completed MP4 clips and SRT captions from the results list.

## Notes and honest limitations
- This is a functional MVP, not the entire advanced roadmap. It does not yet implement a multitrack editor,
  face-follow reframing, speaker diarization, translation, music library, or generated thumbnails.
- Transcription requires the `faster-whisper` model dependency and a model download. Set `WHISPER_MODEL`
  (default `small`) to `base` for faster CPU inference or `medium` for better accuracy with more resources.
- Clip ranking is an explainable heuristic over transcript text and speech density, not a claim of virality.
- YouTube URL ingestion is intentionally not enabled in this MVP. Add only a permitted/authorized source
  integration; do not bypass DRM, access controls, or platform restrictions.
- Uploaded media and rendered clips are stored locally in `backend/data`. Do not expose this server publicly
  without authentication, quotas, file scanning, and hardened storage.
- FFmpeg must be installed separately. The backend checks for it and returns actionable errors.
