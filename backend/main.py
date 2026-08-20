import os
import uuid
import threading
import time
import json
from typing import Optional, List
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from engine.face_swap_engine import FaceSwapEngine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)

app = FastAPI(title="AI Video Face Swap API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}

class JobStatus:
    QUEUED = "queued"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class RegenerateRequest(BaseModel):
    job_id: str
    tuning_preset: Optional[str] = "auto_improve" # 'max_likeness', 'ultra_hd', 'ambient_blend', 'auto_improve', 'custom'
    fidelity: Optional[float] = None
    color_strength: Optional[float] = None
    sharpen_amount: Optional[float] = None
    use_enhancer: Optional[bool] = None
    use_smoothing: Optional[bool] = None
    use_grain: Optional[bool] = None

def run_photo_swap_job(
    job_id: str,
    source_path: str,
    target_path: str,
    use_enhancer: bool,
    use_grain: bool,
    fidelity: float = 0.85,
    color_strength: float = 0.28,
    sharpen_amount: float = 0.15
):
    engine = FaceSwapEngine.get_instance()
    try:
        jobs[job_id]["status"] = JobStatus.INITIALIZING
        jobs[job_id]["message"] = "Initializing AI Face Models..."
        jobs[job_id]["progress"] = 25
        
        if not engine.is_initialized:
            engine.initialize()
            
        jobs[job_id]["status"] = JobStatus.PROCESSING
        jobs[job_id]["message"] = "Analyzing & Swapping Faces with HD Enhancer..."
        jobs[job_id]["progress"] = 65
        
        output_filename = f"swapped_{job_id}.jpg"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        engine.swap_image(
            source_img_path=source_path,
            target_img_path=target_path,
            output_path=output_path,
            use_enhancer=use_enhancer,
            use_grain=use_grain,
            fidelity=fidelity,
            color_strength=color_strength,
            sharpen_amount=sharpen_amount
        )
        
        jobs[job_id]["status"] = JobStatus.COMPLETED
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Photo face swap completed successfully!"
        jobs[job_id]["output_url"] = f"/outputs/{output_filename}"
        jobs[job_id]["download_url"] = f"/api/download/{output_filename}"
        jobs[job_id]["type"] = "photo"
        jobs[job_id]["fidelity"] = fidelity
        jobs[job_id]["color_strength"] = color_strength
        jobs[job_id]["sharpen_amount"] = sharpen_amount
        
    except Exception as e:
        print(f"Photo Job {job_id} error: {e}")
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["error"] = str(e)

def run_video_swap_job(
    job_id: str,
    source_path: str,
    target_path: str,
    max_duration: float,
    target_person_id: Optional[int],
    target_person_embedding: Optional[List[float]],
    use_enhancer: bool,
    use_smoothing: bool,
    use_grain: bool,
    fidelity: float = 0.85,
    color_strength: float = 0.28,
    sharpen_amount: float = 0.15
):
    engine = FaceSwapEngine.get_instance()
    
    try:
        jobs[job_id]["status"] = JobStatus.INITIALIZING
        jobs[job_id]["message"] = "Initializing AI Models..."
        
        def init_callback(percent, msg):
            jobs[job_id]["message"] = msg
            jobs[job_id]["progress"] = int(percent * 0.1)
            
        engine.initialize(progress_callback=init_callback)
        
        jobs[job_id]["status"] = JobStatus.PROCESSING
        jobs[job_id]["message"] = "Processing video frames..."
        
        output_filename = f"swapped_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        def progress_callback(curr_frame, total_frames, percent, eta_str):
            overall_pct = 10 + int(percent * 0.9)
            jobs[job_id]["progress"] = min(99, overall_pct)
            jobs[job_id]["current_frame"] = curr_frame
            jobs[job_id]["total_frames"] = total_frames
            jobs[job_id]["eta"] = eta_str
            jobs[job_id]["message"] = f"Frame {curr_frame}/{total_frames} (ETA: {eta_str})"

        engine.process_video(
            source_img_path=source_path,
            target_video_path=target_path,
            output_video_path=output_path,
            max_duration_sec=max_duration,
            target_person_id=target_person_id,
            target_person_embedding=target_person_embedding,
            use_enhancer=use_enhancer,
            use_smoothing=use_smoothing,
            use_grain=use_grain,
            fidelity=fidelity,
            color_strength=color_strength,
            sharpen_amount=sharpen_amount,
            progress_callback=progress_callback
        )
        
        jobs[job_id]["status"] = JobStatus.COMPLETED
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Face swap completed successfully!"
        jobs[job_id]["output_url"] = f"/outputs/{output_filename}"
        jobs[job_id]["download_url"] = f"/api/download/{output_filename}"
        jobs[job_id]["type"] = "video"
        jobs[job_id]["fidelity"] = fidelity
        jobs[job_id]["color_strength"] = color_strength
        jobs[job_id]["sharpen_amount"] = sharpen_amount
        
    except Exception as e:
        print(f"Job {job_id} error: {e}")
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["error"] = str(e)

@app.on_event("startup")
def on_startup():
    print("Pre-loading AI models (InSwapper + GFPGAN HD) on server startup...")
    try:
        engine = FaceSwapEngine.get_instance()
        engine.initialize()
        print(f"AI Engine Preloaded! InSwapper: {engine.swapper is not None}, GFPGAN 1.4 HD: {engine.enhancer_session is not None}")
    except Exception as e:
        print(f"Preload warning: {e}")

@app.get("/api/status")
def get_engine_status():
    engine = FaceSwapEngine.get_instance()
    return {
        "status": "ready" if engine.is_initialized else "standby",
        "initialized": engine.is_initialized,
        "gfpgan_loaded": engine.enhancer_session is not None,
        "inswapper_loaded": engine.swapper is not None,
        "models": {
            "inswapper": "InSwapper 128 (Loaded)" if engine.swapper is not None else "Standby",
            "gfpgan": "GFPGAN 1.4 HD (Active)" if engine.enhancer_session is not None else "Standby",
            "buffalo_l": "InsightFace Buffalo_L (Active)" if engine.app is not None else "Standby"
        }
    }

@app.post("/api/swap-photo")
async def swap_photo(
    source_files: Optional[List[UploadFile]] = File(None),
    source_file: Optional[UploadFile] = File(None),
    source_template: Optional[str] = Form(None),
    target_file: Optional[UploadFile] = File(None),
    target_template: Optional[str] = Form(None),
    use_enhancer: bool = Form(True),
    use_grain: bool = Form(True)
):
    job_id = str(uuid.uuid4())[:8]
    
    # 1. Source Face Path(s) (Support 1 to 4 uploaded source photos for 3D master fusion)
    src_paths = []
    all_source_uploads = []
    if source_files:
        all_source_uploads.extend([f for f in source_files if f and f.filename])
    if source_file and source_file.filename and source_file not in all_source_uploads:
        all_source_uploads.append(source_file)

    if all_source_uploads:
        for idx, s_file in enumerate(all_source_uploads[:4]):
            src_ext = os.path.splitext(s_file.filename)[1] or ".jpg"
            p = os.path.join(UPLOAD_DIR, f"src_photo_{job_id}_{idx}{src_ext}")
            with open(p, "wb") as f:
                f.write(await s_file.read())
            src_paths.append(p)
    elif source_template:
        t_path = os.path.join(SAMPLES_DIR, source_template)
        if not os.path.exists(t_path):
            raise HTTPException(status_code=404, detail=f"Source template {source_template} not found")
        src_paths.append(t_path)
    else:
        raise HTTPException(status_code=400, detail="Please upload source input photo(s) or select a preset.")

    # 2. Target Photo Path (Right side - Jisme face swap karna h)
    if target_file and target_file.filename:
        tgt_ext = os.path.splitext(target_file.filename)[1] or ".jpg"
        tgt_path = os.path.join(UPLOAD_DIR, f"tgt_photo_{job_id}{tgt_ext}")
        with open(tgt_path, "wb") as f:
            f.write(await target_file.read())
    elif target_template:
        tgt_path = os.path.join(SAMPLES_DIR, target_template)
        if not os.path.exists(tgt_path):
            raise HTTPException(status_code=404, detail=f"Target template {target_template} not found")
    else:
        raise HTTPException(status_code=400, detail="Please upload a target photo or select a preset.")

    primary_src = src_paths[0]
    jobs[job_id] = {
        "id": job_id,
        "type": "photo",
        "status": JobStatus.QUEUED,
        "progress": 0,
        "message": f"Queued with {len(src_paths)} source photo(s) for 3D Identity Fusion...",
        "created_at": time.time(),
        "source_path": primary_src,
        "source_paths": src_paths,
        "target_path": tgt_path,
        "use_enhancer": use_enhancer,
        "use_grain": use_grain,
        "iteration": 1,
        "fidelity": 0.85,
        "color_strength": 0.28,
        "sharpen_amount": 0.15
    }

    thread = threading.Thread(
        target=run_photo_swap_job,
        args=(job_id, src_paths if len(src_paths) > 1 else primary_src, tgt_path, use_enhancer, use_grain, 0.85, 0.28, 0.15),
        daemon=True
    )
    thread.start()

    return {
        "job_id": job_id,
        "type": "photo",
        "iteration": 1,
        "num_sources": len(src_paths),
        "status": "queued",
        "message": f"Photo face swap started with {len(src_paths)} source photo(s)!"
    }

@app.post("/api/extract-video-faces")
async def extract_video_faces(
    target_video: Optional[UploadFile] = File(None),
    target_template: Optional[str] = Form(None)
):
    """
    Extracts all unique people from the uploaded video for selective targeting.
    """
    try:
        temp_id = str(uuid.uuid4())[:8]
        if target_video and target_video.filename:
            ext = os.path.splitext(target_video.filename)[1] or ".mp4"
            vid_path = os.path.join(UPLOAD_DIR, f"temp_detect_{temp_id}{ext}")
            with open(vid_path, "wb") as f:
                f.write(await target_video.read())
        elif target_template:
            vid_path = os.path.join(SAMPLES_DIR, target_template)
            if not os.path.exists(vid_path):
                raise HTTPException(status_code=404, detail="Template video not found")
        else:
            raise HTTPException(status_code=400, detail="No video provided")

        engine = FaceSwapEngine.get_instance()
        if not engine.is_initialized:
            engine.initialize()

        faces = engine.extract_unique_faces_from_video(vid_path, UPLOAD_DIR)
        return {
            "status": "success",
            "faces": faces
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/swap-video")
async def swap_video(
    source_files: Optional[List[UploadFile]] = File(None),
    source_file: Optional[UploadFile] = File(None),
    source_template: Optional[str] = Form(None),
    target_video: Optional[UploadFile] = File(None),
    target_template: Optional[str] = Form(None),
    max_duration: float = Form(30.0),
    target_person_id: Optional[int] = Form(None),
    target_person_embedding: Optional[str] = Form(None),
    use_enhancer: bool = Form(True),
    use_smoothing: bool = Form(True),
    use_grain: bool = Form(True)
):
    job_id = str(uuid.uuid4())[:8]
    
    # 1. Source Face Path(s)
    src_paths = []
    all_source_uploads = []
    if source_files:
        all_source_uploads.extend([f for f in source_files if f and f.filename])
    if source_file and source_file.filename and source_file not in all_source_uploads:
        all_source_uploads.append(source_file)

    if all_source_uploads:
        for idx, s_file in enumerate(all_source_uploads[:4]):
            src_ext = os.path.splitext(s_file.filename)[1] or ".jpg"
            p = os.path.join(UPLOAD_DIR, f"src_vid_{job_id}_{idx}{src_ext}")
            with open(p, "wb") as f:
                f.write(await s_file.read())
            src_paths.append(p)
    elif source_template:
        t_path = os.path.join(SAMPLES_DIR, source_template)
        if not os.path.exists(t_path):
            raise HTTPException(status_code=404, detail=f"Source template {source_template} not found")
        src_paths.append(t_path)
    else:
        raise HTTPException(status_code=400, detail="Please upload a source face photo or select a template.")

    # 2. Target Video Path
    if target_video and target_video.filename:
        tgt_ext = os.path.splitext(target_video.filename)[1] or ".mp4"
        tgt_path = os.path.join(UPLOAD_DIR, f"tgt_{job_id}{tgt_ext}")
        with open(tgt_path, "wb") as f:
            f.write(await target_video.read())
    elif target_template:
        tgt_path = os.path.join(SAMPLES_DIR, target_template)
        if not os.path.exists(tgt_path):
            raise HTTPException(status_code=404, detail=f"Target template {target_template} not found")
    else:
        raise HTTPException(status_code=400, detail="Please upload a target video or select a sample video.")

    max_duration = min(30.0, max(1.0, float(max_duration)))

    emb_list = None
    if target_person_embedding:
        try:
            emb_list = json.loads(target_person_embedding)
        except:
            emb_list = None

    primary_src = src_paths[0]
    jobs[job_id] = {
        "id": job_id,
        "type": "video",
        "status": JobStatus.QUEUED,
        "progress": 0,
        "current_frame": 0,
        "total_frames": 0,
        "eta": "Calculating...",
        "message": f"Job queued with {len(src_paths)} source photo(s)...",
        "created_at": time.time(),
        "source_path": primary_src,
        "source_paths": src_paths,
        "target_path": tgt_path,
        "max_duration": max_duration,
        "target_person_id": target_person_id,
        "target_person_embedding": emb_list,
        "use_enhancer": use_enhancer,
        "use_smoothing": use_smoothing,
        "use_grain": use_grain,
        "iteration": 1,
        "fidelity": 0.85,
        "color_strength": 0.28,
        "sharpen_amount": 0.15
    }

    thread = threading.Thread(
        target=run_video_swap_job,
        args=(job_id, src_paths if len(src_paths) > 1 else primary_src, tgt_path, max_duration, target_person_id, emb_list, use_enhancer, use_smoothing, use_grain, 0.85, 0.28, 0.15),
        daemon=True
    )
    thread.start()

    return {
        "job_id": job_id,
        "type": "video",
        "iteration": 1,
        "num_sources": len(src_paths),
        "status": "queued",
        "message": f"Video face swap started with {len(src_paths)} source photo(s)!"
    }

@app.post("/api/regenerate")
async def regenerate_swap(req: RegenerateRequest):
    """
    Regenerates previous photo/video face swap with customized AI hyperparameter tuning
    based on user satisfaction feedback (e.g. Max Likeness, Ultra-HD, Ambient Glow, Auto-Improve).
    """
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Previous job not found. Please upload fresh media.")
    
    prev_job = jobs[req.job_id]
    src_paths = prev_job.get("source_paths") or [prev_job.get("source_path")]
    src_path = src_paths if len(src_paths) > 1 else src_paths[0]
    tgt_path = prev_job.get("target_path")
    
    if not src_paths or not os.path.exists(src_paths[0]) or not tgt_path or not os.path.exists(tgt_path):
        raise HTTPException(status_code=400, detail="Original source or target files are no longer available.")
        
    new_job_id = str(uuid.uuid4())[:8]
    job_type = prev_job.get("type", "photo")
    prev_iteration = prev_job.get("iteration", 1)
    new_iteration = prev_iteration + 1
    
    preset = req.tuning_preset or "auto_improve"
    use_enhancer = prev_job.get("use_enhancer", True) if req.use_enhancer is None else req.use_enhancer
    use_grain = prev_job.get("use_grain", True) if req.use_grain is None else req.use_grain
    use_smoothing = prev_job.get("use_smoothing", True) if req.use_smoothing is None else req.use_smoothing

    if preset == "max_likeness":
        # Strict preservation of original face identity & natural complexion
        fidelity = 0.95
        color_strength = 0.16
        sharpen_amount = 0.20
        preset_title = "Max Input Likeness (100% Face Identity Match)"
    elif preset == "ultra_hd":
        # Maximum GFPGAN pore restoration & crisp eye sharpness
        fidelity = 0.92
        color_strength = 0.26
        sharpen_amount = 0.32
        preset_title = "Ultra-HD & Sharp Eyes (Max GFPGAN Detail)"
    elif preset == "ambient_blend":
        # Natural lighting blend with scene
        fidelity = 0.82
        color_strength = 0.38
        sharpen_amount = 0.10
        preset_title = "Cinematic Ambient Lighting & Seamless Blend"
    elif preset == "auto_improve":
        # Progressive improvement pass
        fidelity = min(0.96, 0.85 + (new_iteration - 1) * 0.05)
        color_strength = max(0.18, 0.28 - (new_iteration - 1) * 0.04)
        sharpen_amount = min(0.30, 0.15 + (new_iteration - 1) * 0.05)
        preset_title = f"Smart AI Improvement (Iteration {new_iteration})"
    else: # custom sliders
        fidelity = req.fidelity if req.fidelity is not None else 0.88
        color_strength = req.color_strength if req.color_strength is not None else 0.24
        sharpen_amount = req.sharpen_amount if req.sharpen_amount is not None else 0.18
        preset_title = "Custom User Fine-Tuning"

    jobs[new_job_id] = {
        "id": new_job_id,
        "type": job_type,
        "status": JobStatus.QUEUED,
        "progress": 0,
        "message": f"Regenerating ({preset_title})...",
        "created_at": time.time(),
        "source_path": src_path,
        "target_path": tgt_path,
        "parent_job_id": req.job_id,
        "iteration": new_iteration,
        "preset": preset,
        "preset_title": preset_title,
        "fidelity": fidelity,
        "color_strength": color_strength,
        "sharpen_amount": sharpen_amount,
        "use_enhancer": use_enhancer,
        "use_grain": use_grain,
        "use_smoothing": use_smoothing
    }

    if job_type == "photo":
        thread = threading.Thread(
            target=run_photo_swap_job,
            args=(new_job_id, src_path, tgt_path, use_enhancer, use_grain, fidelity, color_strength, sharpen_amount),
            daemon=True
        )
        thread.start()
    else:
        max_duration = prev_job.get("max_duration", 30.0)
        target_person_id = prev_job.get("target_person_id")
        target_person_embedding = prev_job.get("target_person_embedding")
        jobs[new_job_id]["max_duration"] = max_duration
        jobs[new_job_id]["target_person_id"] = target_person_id
        jobs[new_job_id]["target_person_embedding"] = target_person_embedding
        
        thread = threading.Thread(
            target=run_video_swap_job,
            args=(new_job_id, src_path, tgt_path, max_duration, target_person_id, target_person_embedding, use_enhancer, use_smoothing, use_grain, fidelity, color_strength, sharpen_amount),
            daemon=True
        )
        thread.start()

    return {
        "job_id": new_job_id,
        "type": job_type,
        "iteration": new_iteration,
        "preset": preset,
        "preset_title": preset_title,
        "status": "queued",
        "message": f"Regenerating face swap with {preset_title}..."
    }

@app.get("/api/job/{job_id}")
def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/templates")
def get_templates():
    sample_faces = []
    sample_targets = []
    sample_videos = []
    
    if os.path.exists(SAMPLES_DIR):
        for f in os.listdir(SAMPLES_DIR):
            name_lower = f.lower()
            if name_lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                item = {
                    "id": f,
                    "title": f.rsplit(".", 1)[0].replace("_", " ").title(),
                    "url": f"/samples/{f}"
                }
                if name_lower.startswith("target_") or "target" in name_lower or "scene" in name_lower:
                    sample_targets.append(item)
                else:
                    sample_faces.append(item)
            elif name_lower.endswith(('.mp4', '.webm', '.mov')):
                sample_videos.append({
                    "id": f,
                    "title": f.rsplit(".", 1)[0].replace("_", " ").title(),
                    "url": f"/samples/{f}"
                })
                
    return {
        "faces": sample_faces,
        "target_photos": sample_targets,
        "videos": sample_videos
    }

@app.get("/api/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    media_type = "image/jpeg" if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) else "video/mp4"
    return FileResponse(file_path, media_type=media_type, filename=filename)

app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

