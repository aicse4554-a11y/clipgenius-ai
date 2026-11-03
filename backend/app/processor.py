from __future__ import annotations
import json, re, shutil, subprocess
from pathlib import Path
from collections import Counter

HOOK_WORDS = {"why", "how", "secret", "mistake", "never", "always", "truth", "important",
              "imagine", "remember", "because", "problem", "solution", "surprising"}
def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "Command failed")[-1800:])
    return result.stdout

def probe_video(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe is not installed. Install FFmpeg and ensure ffprobe is on PATH.")
    raw = run(["ffprobe", "-v", "error", "-show_entries",
               "format=duration,size:stream=codec_type,width,height",
               "-of", "json", str(path)])
    data = json.loads(raw)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {
        "duration": round(float(data.get("format", {}).get("duration", 0)), 2),
        "width": video.get("width"), "height": video.get("height"),
        "resolution": f'{video.get("width", "?")}×{video.get("height", "?")}',
        "size_bytes": int(data.get("format", {}).get("size", path.stat().st_size))
    }

def srt_time(seconds: float) -> str:
    ms = max(0, int(seconds * 1000))
    h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def transcribe(path: Path):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Faster-Whisper is missing. Install backend/requirements.txt and retry.") from exc
    model_name = __import__("os").environ.get("WHISPER_MODEL", "small")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), vad_filter=True, word_timestamps=True)
    out = []
    for seg in segments:
        words = []
        if seg.words:
            words = [{"start": float(w.start), "end": float(w.end), "text": w.word} for w in seg.words]
        out.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip(), "words": words})
    if not out:
        raise RuntimeError("No speech was detected in this video.")
    return out

def make_candidates(segments: list[dict], duration: float, clip_seconds: int):
    # Candidate windows begin at transcript segments. Score is a heuristic, never a virality guarantee.
    candidates = []
    for i, seg in enumerate(segments):
        start = max(0, float(seg["start"]) - 1.0)
        end_limit = min(duration, start + clip_seconds)
        chosen, text_parts = [], []
        for item in segments[i:]:
            if item["start"] >= end_limit: break
            if item["end"] > start:
                chosen.append(item); text_parts.append(item["text"])
        if not chosen: continue
        end = min(duration, max(float(x["end"]) for x in chosen) + 0.5)
        if end - start < min(8, clip_seconds * .45): continue
        text = " ".join(text_parts)
        words = re.findall(r"\b[\w']+\b", text.lower())
        density = min(1.0, len(words) / max(1, (end-start)*2.2))
        hooks = sum(1 for w in words if w in HOOK_WORDS)
        questions = text.count("?")
        emphatic = sum(1 for w in words if w.isupper() and len(w) > 2)
        score = min(98, round(38 + density*28 + min(hooks, 4)*5 + min(questions, 2)*3 + min(emphatic, 3)*2))
        reason = []
        if hooks: reason.append("contains attention-grabbing language")
        if questions: reason.append("uses a question to create curiosity")
        if density > .55: reason.append("has a strong speaking pace")
        if not reason: reason.append("contains a self-contained stretch of speech")
        candidates.append({"start": round(start,2), "end": round(end,2), "text": text,
                           "score": score, "reason": ", ".join(reason)})
    # Deduplicate overlapping windows, keeping the strongest.
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    for c in candidates:
        if all(c["end"] <= s["start"] or c["start"] >= s["end"] for s in selected):
            selected.append(c)
        if len(selected) >= 8: break
    return sorted(selected, key=lambda x: x["score"], reverse=True)

def write_srt(segments: list[dict], start: float, end: float, target: Path):
    lines, idx = [], 1
    for seg in segments:
        if seg["end"] <= start or seg["start"] >= end: continue
        a, b = max(start, seg["start"]), min(end, seg["end"])
        lines += [str(idx), f"{srt_time(a-start)} --> {srt_time(b-start)}", seg["text"], ""]
        idx += 1
    target.write_text("\n".join(lines), encoding="utf-8")

def process_video(source: Path, out_dir: Path, clip_seconds: int, update):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is not installed. Install FFmpeg and ensure it is on PATH.")
    out_dir.mkdir(parents=True, exist_ok=True)
    update("Transcribing speech with Faster-Whisper", 12)
    segments = transcribe(source)
    duration = probe_video(source)["duration"]
    update("Finding and scoring highlight moments", 58)
    candidates = make_candidates(segments, duration, clip_seconds)
    if not candidates:
        raise RuntimeError("No suitable speech windows were found. Try a longer clip duration or a video with clearer speech.")
    results = []
    for index, c in enumerate(candidates, 1):
        update(f"Rendering clip {index} of {len(candidates)}", 62 + int(34 * (index-1)/len(candidates)))
        stem = f"clip-{index:02d}"
        mp4, srt = out_dir / f"{stem}.mp4", out_dir / f"{stem}.srt"
        run(["ffmpeg", "-y", "-ss", str(c["start"]), "-i", str(source), "-t",
             str(c["end"]-c["start"]), "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-movflags", "+faststart", str(mp4)])
        write_srt(segments, c["start"], c["end"], srt)
        results.append({"id": stem, "filename": mp4.name, "subtitle": srt.name,
                        "start": c["start"], "end": c["end"], "duration": round(c["end"]-c["start"],1),
                        "score": c["score"], "reason": c["reason"], "transcript": c["text"]})
    update("Finalizing results", 98)
    return results
