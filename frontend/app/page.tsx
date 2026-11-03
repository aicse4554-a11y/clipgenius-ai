"use client";
import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
type Clip = {id:string;filename:string;subtitle:string;start:number;end:number;duration:number;score:number;reason:string;transcript:string};
type Project = {id:string;name:string;size_bytes:number;metadata:{duration:number;resolution:string};status:string;stage:string;progress:number;clips:Clip[];error?:string|null};
const fmt = (n:number) => `${Math.floor(n/60)}:${String(Math.floor(n%60)).padStart(2,"0")}`;
const bytes = (n:number) => n > 1e9 ? `${(n/1e9).toFixed(2)} GB` : `${(n/1e6).toFixed(1)} MB`;

export default function Home() {
  const [project,setProject] = useState<Project|null>(null);
  const [projects,setProjects] = useState<Project[]>([]);
  const [duration,setDuration] = useState(30);
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState("");
  const [health,setHealth] = useState<{ffmpeg:boolean;ffprobe:boolean}|null>(null);
  const input = useRef<HTMLInputElement>(null);
  async function refreshList() {
    try { const r=await fetch(`${API}/api/projects`); if(r.ok) setProjects(await r.json()); } catch {}
  }
  useEffect(()=>{ refreshList(); fetch(`${API}/api/health`).then(r=>r.json()).then(setHealth).catch(()=>setHealth(null)); },[]);
  useEffect(()=>{
    if(!project || !["queued","processing"].includes(project.status)) return;
    const timer=setInterval(async()=>{
      try { const r=await fetch(`${API}/api/projects/${project.id}`); if(r.ok){const p=await r.json();setProject(p);if(["completed","failed"].includes(p.status)){setBusy(false);refreshList();}} } catch {}
    },1800);
    return ()=>clearInterval(timer);
  },[project?.id,project?.status]);
  async function upload(file?:File) {
    if(!file) return;
    setBusy(true); setMessage("Uploading and inspecting video…");
    const data=new FormData(); data.append("file",file);
    try {
      const r=await fetch(`${API}/api/projects`,{method:"POST",body:data});
      const p=await r.json(); if(!r.ok) throw new Error(p.detail||"Upload failed");
      setProject(p);setMessage("Video ready. Choose a duration and find highlights.");refreshList();
    } catch(e:any){setMessage(e.message||"Could not upload video.");}
    finally{setBusy(false);}
  }
  async function analyze() {
    if(!project)return;
    setBusy(true);setMessage("Starting real transcription and clip generation…");
    try {
      const r=await fetch(`${API}/api/projects/${project.id}/analyze?clip_seconds=${duration}`,{method:"POST"});
      const p=await r.json();if(!r.ok)throw new Error(p.detail||"Could not start processing");
      setProject(p);setMessage("Processing started. You can keep this page open while the local worker runs.");
    } catch(e:any){setMessage(e.message||"Could not start processing.");setBusy(false);}
  }
  async function loadProject(id:string) {
    const r=await fetch(`${API}/api/projects/${id}`);if(r.ok)setProject(await r.json());
  }
  return <main className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brandIcon">✦</div><span>clipgenius<span className="accent">.ai</span></span></div>
      <div className="navLabel">WORKSPACE</div><div className="nav active">▦　 Overview</div><div className="nav">◫　 AI Clip Studio</div><div className="nav">▤　 My projects</div>
      <div className="sideBottom"><div className="freeTag">✦ FREE & OPEN</div><p>Local-first video intelligence. Your media stays on your machine.</p><div className="avatar">CG</div></div>
    </aside>
    <section className="main">
      <header><div><div className="eyebrow">YOUR CREATIVE WORKSPACE</div><h1>Turn long videos into <span className="gradient">great moments.</span></h1><p className="sub">Find the moments worth sharing. Create clips in minutes.</p></div><div className="topPill"><span className="liveDot"/> LOCAL ENGINE</div></header>
      <div className="stats">
        <div className="stat"><span>PROJECTS</span><strong>{projects.length}</strong><small>Saved on this device</small></div>
        <div className="stat"><span>CLIPS GENERATED</span><strong>{projects.reduce((n,p)=>n+(p.clips?.length||0),0)}</strong><small>Ready to download</small></div>
        <div className="stat"><span>PROCESSING ENGINE</span><strong className="engine">{health?.ffmpeg&&health?.ffprobe?"Ready":"Check setup"}</strong><small>{health?.ffmpeg?"FFmpeg detected":"FFmpeg not detected"}</small></div>
      </div>
      <div className="workspace">
        <section className="panel uploadPanel">
          <div className="panelHead"><div><div className="eyebrow">START A PROJECT</div><h2>Bring your video</h2></div><span className="step">01 / INPUT</span></div>
          <button className="dropzone" onClick={()=>input.current?.click()} disabled={busy}>
            <div className="uploadIcon">↑</div><strong>Drop your video here</strong><span>or click to browse your device</span><small>MP4 · MOV · WEBM · MKV · up to 8 GB</small>
          </button>
          <input ref={input} type="file" accept="video/*,.mkv" hidden onChange={e=>upload(e.target.files?.[0])}/>
          {project && <div className="fileCard"><div className="fileIcon">▶</div><div className="fileInfo"><strong>{project.name}</strong><span>{project.metadata.resolution} · {fmt(project.metadata.duration)} · {bytes(project.size_bytes)}</span></div><span className="ready">READY</span></div>}
          <div className="settingRow"><div><strong>Target clip length</strong><span>We'll find the strongest moments around this duration.</span></div><select value={duration} onChange={e=>setDuration(Number(e.target.value))}>{[15,30,45,60,90].map(n=><option key={n} value={n}>{n} seconds</option>)}</select></div>
          <button className="primary" onClick={analyze} disabled={!project||busy||["queued","processing"].includes(project.status)}>{busy?"Working…":"✦　 Find my best moments"}</button>
          {message && <p className="message">{message}</p>}
          {project && ["queued","processing"].includes(project.status) && <div className="progressBox"><div className="progressText"><b>{project.stage}</b><span>{project.progress}%</span></div><div className="track"><i style={{width:`${project.progress}%`}}/></div><small>Processing is running locally. Do not close the backend terminal.</small></div>}
          {project?.status==="failed" && <div className="error">{project.error}</div>}
        </section>
        <section className="panel resultsPanel">
          <div className="panelHead"><div><div className="eyebrow">AI HIGHLIGHTS</div><h2>Your clip collection</h2></div><span className="step">{project?.clips?.length||0} CLIPS</span></div>
          {!project?.clips?.length ? <div className="empty"><div className="emptyGlyph">✧</div><strong>Your best moments will appear here</strong><span>Upload a video and let ClipGenius analyze the story, pacing, and standout moments.</span></div> :
            <div className="clipList">{project.clips.map((c,i)=><article className="clip" key={c.id}><div className="clipNum">{String(i+1).padStart(2,"0")}</div><div className="clipBody"><div className="clipTitle">Highlight {i+1}<span>{fmt(c.duration)}</span></div><p>{c.transcript}</p><small>{c.reason}</small><div className="scoreLine"><div className="scoreTrack"><i style={{width:`${c.score}%`}}/></div><b>{c.score}/100</b></div><div className="downloadRow"><a href={`${API}/api/projects/${project.id}/clips/${c.filename}`}>↓ MP4</a><a href={`${API}/api/projects/${project.id}/clips/${c.subtitle}`}>↓ SRT captions</a></div></div></article>)}</div>}
        </section>
      </div>
      <section className="panel recent"><div className="panelHead"><div><div className="eyebrow">LIBRARY</div><h2>Recent projects</h2></div></div>
        {projects.length===0?<p className="muted">Your uploaded projects will be saved here on this device.</p>:<div className="projectRows">{projects.map(p=><button key={p.id} onClick={()=>loadProject(p.id)} className={`projectRow ${project?.id===p.id?"selected":""}`}><span className="projectPlay">▶</span><span className="projectName">{p.name}<small>{p.metadata?.resolution} · {fmt(p.metadata?.duration||0)}</small></span><span className={`status ${p.status}`}>{p.status}</span><span>›</span></button>)}</div>}
      </section>
      <footer><span>✦ CLIPGENIUS AI</span><span>Free. Local-first. No watermark. No subscriptions.</span></footer>
    </section>
  </main>;
}
