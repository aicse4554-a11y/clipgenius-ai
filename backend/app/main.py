from __future__ import annotations
import json, os, shutil, uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .processor import probe_video, process_video

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
OUTPUTS = DATA / "outputs"
JOBS = DATA / "jobs"
for folder in (UPLOADS, OUTPUTS, JOBS):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ClipGenius AI API", version="0.1.0")
cors_origins = [x.strip() for x in os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

ALLOWED = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}

def job_path(job_id: str) -> Path:
    return JOBS / f"{job_id}.json"

def read_job(job_id: str) -> dict:
    path = job_path(job_id)
    if not path.exists():
        raise HTTPException(404, "Project not found")
    return json.loads(path.read_text())

def write_job(job: dict) -> None:
    job_path(job["id"]).write_text(json.dumps(job, indent=2))

@app.get("/api/health")
def health():
    return {"status": "ok", "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None}

@app.post("/api/projects")
async def create_project(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, f"Unsupported format {suffix or '(none)'}. Use MP4, MOV, WEBM, MKV, M4V, or AVI.")
    project_id = str(uuid.uuid4())
    safe_name = f"{project_id}{suffix}"
    target = UPLOADS / safe_name
    size = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 8 * 1024 * 1024 * 1024:
                    raise HTTPException(413, "File exceeds the 8 GB MVP upload limit.")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    try:
        metadata = probe_video(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not read this video. Check FFmpeg installation and file integrity. Details: {exc}")
    job = {
        "id": project_id, "name": file.filename or safe_name, "file": safe_name,
        "size_bytes": size, "metadata": metadata, "status": "uploaded",
        "stage": "Ready to analyze", "progress": 0, "clips": [], "error": None
    }
    write_job(job)
    return job

@app.get("/api/projects")
def list_projects():
    items = [json.loads(p.read_text()) for p in JOBS.glob("*.json")]
    return sorted(items, key=lambda x: x.get("id", ""), reverse=True)

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return read_job(project_id)

@app.post("/api/projects/{project_id}/analyze")
def analyze(project_id: str, background: BackgroundTasks, clip_seconds: int = 30):
    if clip_seconds not in (15, 30, 45, 60, 90):
        raise HTTPException(400, "Clip duration must be 15, 30, 45, 60, or 90 seconds.")
    job = read_job(project_id)
    if job["status"] in ("processing",):
        raise HTTPException(409, "This project is already processing.")
    job.update(status="queued", stage="Waiting for worker", progress=0, error=None, clips=[])
    write_job(job)
    background.add_task(run_processing, project_id, clip_seconds)
    return job

def run_processing(project_id: str, clip_seconds: int):
    job = read_job(project_id)
    source = UPLOADS / job["file"]
    def update(stage: str, progress: int):
        current = read_job(project_id)
        current.update(status="processing", stage=stage, progress=progress)
        write_job(current)
    try:
        clips = process_video(source, OUTPUTS / project_id, clip_seconds, update)
        current = read_job(project_id)
        current.update(status="completed", stage="Finished", progress=100, clips=clips)
        write_job(current)
    except Exception as exc:
        current = read_job(project_id)
        current.update(status="failed", stage="Processing failed", error=str(exc))
        write_job(current)

@app.get("/api/projects/{project_id}/clips/{filename}")
def download_clip(project_id: str, filename: str):
    if Path(filename).name != filename:
        raise HTTPException(400, "Invalid filename")
    path = OUTPUTS / project_id / filename
    if not path.is_file():
        raise HTTPException(404, "Clip not found")
    media = "text/plain" if filename.endswith(".srt") else "video/mp4"
    return FileResponse(path, media_type=media, filename=filename)
