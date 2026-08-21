import os
import sys
import uuid
import threading
import time
import json
import base64
import cv2
import numpy as np
from typing import Optional, List, Dict, Any, Union
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    from engine.face_swap_engine import FaceSwapEngine
except ImportError:
    from backend.engine.face_swap_engine import FaceSwapEngine

try:
    from virtual_cam_manager import VirtualCamManager
except ImportError:
    from backend.virtual_cam_manager import VirtualCamManager

BASE_DIR = os.path.dirname(BACKEND_DIR)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Pre-loading AI models (InSwapper + GFPGAN HD) on server startup...")
    try:
        engine = FaceSwapEngine.get_instance()
        engine.initialize()
        print(f"AI Engine Preloaded! InSwapper: {engine.swapper is not None}, GFPGAN 1.4 HD: {engine.enhancer_session is not None}")
    except Exception as e:
        print(f"Preload warning: {e}")
    yield

app = FastAPI(title="AI Video Face Swap API", version="1.0.0", lifespan=lifespan)


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
    fidelity: float = 0.92,
    color_strength: float = 0.15,
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
            source_img_paths=source_path,
            target_img_path=target_path,
            output_path=output_path,
            use_enhancer=use_enhancer,
            use_grain=use_grain,
            fidelity=fidelity,
            color_strength=color_strength,
            sharpen_amount=sharpen_amount,
            multi_person_sources=jobs[job_id].get("multi_person_sources")
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
    source_path: Any,
    target_path: str,
    max_duration: float,
    start_offset: float = 0.0,
    part_number: int = 1,
    target_person_id: Optional[int] = None,
    target_person_embedding: Optional[List[float]] = None,
    use_enhancer: bool = True,
    use_smoothing: bool = True,
    use_grain: bool = True,
    fidelity: float = 0.92,
    color_strength: float = 0.15,
    sharpen_amount: float = 0.15
):
    engine = FaceSwapEngine.get_instance()
    
    try:
        jobs[job_id]["status"] = JobStatus.INITIALIZING
        jobs[job_id]["message"] = f"Initializing AI Models (Part {part_number})..."
        
        def init_callback(percent, msg):
            jobs[job_id]["message"] = msg
            jobs[job_id]["progress"] = int(percent * 0.1)
            
        engine.initialize(progress_callback=init_callback)
        
        jobs[job_id]["status"] = JobStatus.PROCESSING
        jobs[job_id]["message"] = f"Processing Part {part_number} frames..."
        
        output_filename = f"swapped_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        def progress_callback(curr_frame, total_frames, percent, eta_str, preview_img=None):
            overall_pct = 10 + int(percent * 0.9)
            jobs[job_id]["progress"] = min(99, overall_pct)
            jobs[job_id]["current_frame"] = curr_frame
            jobs[job_id]["total_frames"] = total_frames
            jobs[job_id]["eta"] = eta_str
            jobs[job_id]["message"] = f"Part {part_number} • Frame {curr_frame}/{total_frames} (ETA: {eta_str})"

            if preview_img is not None:
                try:
                    h, w = preview_img.shape[:2]
                    scale = min(1.0, 360.0 / max(1, w))
                    thumb = cv2.resize(preview_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1.0 else preview_img
                    ret, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ret:
                        jobs[job_id]["preview_frame"] = base64.b64encode(buf).decode("ascii")
                except Exception as ex:
                    pass


        engine.process_video(
            source_img_paths=source_path,
            target_video_path=target_path,
            output_video_path=output_path,
            max_duration_sec=max_duration,
            start_offset_sec=start_offset,
            target_person_id=target_person_id,
            target_person_embedding=target_person_embedding,
            use_enhancer=use_enhancer,
            use_smoothing=use_smoothing,
            use_grain=use_grain,
            fidelity=fidelity,
            color_strength=color_strength,
            sharpen_amount=sharpen_amount,
            progress_callback=progress_callback,
            multi_person_sources=jobs[job_id].get("multi_person_sources")
        )
        
        jobs[job_id]["status"] = JobStatus.COMPLETED
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = f"Part {part_number} completed successfully!"
        jobs[job_id]["output_url"] = f"/outputs/{output_filename}"
        jobs[job_id]["download_url"] = f"/api/download/{output_filename}"
        jobs[job_id]["output_filename"] = output_filename
        jobs[job_id]["output_path"] = output_path
        jobs[job_id]["type"] = "video"
        jobs[job_id]["part_number"] = part_number
        jobs[job_id]["start_offset"] = start_offset
        jobs[job_id]["duration"] = max_duration
        jobs[job_id]["fidelity"] = fidelity
        jobs[job_id]["color_strength"] = color_strength
        jobs[job_id]["sharpen_amount"] = sharpen_amount
        
    except Exception as e:
        print(f"Video Job {job_id} error: {e}")
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["error"] = str(e)


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
    source_file: Optional[UploadFile] = File(None),
    source_files: Optional[List[UploadFile]] = File(None),
    source_person_0_files: Optional[List[UploadFile]] = File(None),
    source_person_1_files: Optional[List[UploadFile]] = File(None),
    source_person_2_files: Optional[List[UploadFile]] = File(None),
    source_person_3_files: Optional[List[UploadFile]] = File(None),
    source_template: Optional[str] = Form(None),
    target_file: Optional[UploadFile] = File(None),
    target_template: Optional[str] = Form(None),
    use_enhancer: bool = Form(True),
    use_grain: bool = Form(True)
):
    job_id = str(uuid.uuid4())[:8]
    engine = FaceSwapEngine.get_instance()
    engine.initialize()
    
    # 1. Multi-Person Sources Check
    multi_person_sources = []
    person_buckets = [source_person_0_files, source_person_1_files, source_person_2_files, source_person_3_files]
    
    for p_idx, p_files in enumerate(person_buckets):
        if p_files and len(p_files) > 0 and any(f.filename for f in p_files):
            p_paths = []
            for f_idx, pf in enumerate([f for f in p_files if f.filename][:4]):
                src_ext = os.path.splitext(pf.filename)[1] or ".jpg"
                p = os.path.join(UPLOAD_DIR, f"src_p{p_idx}_{job_id}_{f_idx}{src_ext}")
                with open(p, "wb") as f:
                    f.write(await pf.read())
                p_paths.append(p)
            if p_paths:
                imgs = [cv2.imread(x) for x in p_paths if cv2.imread(x) is not None]
                if imgs:
                    s_face = engine.get_face(imgs[0])
                    s_emb = engine.get_multi_source_master_embedding(imgs)
                    multi_person_sources.append({
                        'person_idx': p_idx,
                        'source_face': s_face,
                        'source_embedding': s_emb,
                        'source_paths': p_paths
                    })

    # Standard Single-Person fallback
    src_paths = []
    if not multi_person_sources:
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
    else:
        src_paths = multi_person_sources[0]['source_paths']

    # 2. Target Photo Path
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
        "message": f"Queued with {len(multi_person_sources) if multi_person_sources else len(src_paths)} person face(s)...",
        "created_at": time.time(),
        "source_path": primary_src,
        "source_paths": src_paths,
        "multi_person_sources": multi_person_sources,
        "target_path": tgt_path,
        "use_enhancer": use_enhancer,
        "use_grain": use_grain,
        "iteration": 1,
        "fidelity": 0.92,
        "color_strength": 0.15,
        "sharpen_amount": 0.15
    }

    thread = threading.Thread(
        target=run_photo_swap_job,
        args=(
            job_id,
            src_paths,
            tgt_path,
            use_enhancer,
            use_grain,
            0.92,
            0.15,
            0.15
        ),
        daemon=True
    )
    thread.start()
    
    return {"job_id": job_id, "status": "queued"}

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
    source_file: Optional[UploadFile] = File(None),
    source_files: Optional[List[UploadFile]] = File(None),
    source_person_0_files: Optional[List[UploadFile]] = File(None),
    source_person_1_files: Optional[List[UploadFile]] = File(None),
    source_person_2_files: Optional[List[UploadFile]] = File(None),
    source_person_3_files: Optional[List[UploadFile]] = File(None),
    source_template: Optional[str] = Form(None),
    target_video: Optional[UploadFile] = File(None),
    target_template: Optional[str] = Form(None),
    max_duration: float = Form(30.0),
    start_offset: float = Form(0.0),
    part_number: int = Form(1),
    target_person_id: Optional[int] = Form(None),
    target_person_embedding: Optional[str] = Form(None),
    use_enhancer: bool = Form(False),
    use_smoothing: bool = Form(True),
    use_grain: bool = Form(True)
):
    job_id = str(uuid.uuid4())[:8]
    engine = FaceSwapEngine.get_instance()
    engine.initialize()
    
    # 1. Multi-Person Sources Check
    multi_person_sources = []
    person_buckets = [source_person_0_files, source_person_1_files, source_person_2_files, source_person_3_files]
    
    for p_idx, p_files in enumerate(person_buckets):
        if p_files and len(p_files) > 0 and any(f.filename for f in p_files):
            p_paths = []
            for f_idx, pf in enumerate([f for f in p_files if f.filename][:4]):
                src_ext = os.path.splitext(pf.filename)[1] or ".jpg"
                p = os.path.join(UPLOAD_DIR, f"src_p{p_idx}_{job_id}_{f_idx}{src_ext}")
                with open(p, "wb") as f:
                    f.write(await pf.read())
                p_paths.append(p)
            if p_paths:
                imgs = [cv2.imread(x) for x in p_paths if cv2.imread(x) is not None]
                if imgs:
                    s_face = engine.get_face(imgs[0])
                    s_emb = engine.get_multi_source_master_embedding(imgs)
                    multi_person_sources.append({
                        'person_idx': p_idx,
                        'source_face': s_face,
                        'source_embedding': s_emb,
                        'source_paths': p_paths
                    })

    # Standard Single-Person fallback
    src_paths = []
    if not multi_person_sources:
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
            raise HTTPException(status_code=400, detail="Please upload source input photo(s) or select a preset.")
    else:
        src_paths = multi_person_sources[0]['source_paths']

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

    # Calculate video total duration
    cap_temp = cv2.VideoCapture(tgt_path)
    fps_temp = cap_temp.get(cv2.CAP_PROP_FPS) or 25.0
    frames_temp = cap_temp.get(cv2.CAP_PROP_FRAME_COUNT)
    total_video_duration = frames_temp / fps_temp if frames_temp > 0 else 30.0
    cap_temp.release()

    start_offset = max(0.0, float(start_offset))
    part_number = max(1, int(part_number))
    chunk_duration = min(30.0, max(1.0, float(max_duration)))
    
    end_offset = min(total_video_duration, start_offset + chunk_duration)
    has_more_parts = (total_video_duration > start_offset + chunk_duration) and (start_offset + chunk_duration < 120.0)
    next_start_offset = start_offset + chunk_duration if has_more_parts else None

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
        "message": f"Part {part_number} queued with {len(src_paths)} source photo(s)...",
        "created_at": time.time(),
        "source_path": primary_src,
        "source_paths": src_paths,
        "target_path": tgt_path,
        "max_duration": chunk_duration,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "part_number": part_number,
        "total_video_duration": total_video_duration,
        "has_more_parts": has_more_parts,
        "next_start_offset": next_start_offset,
        "target_person_id": target_person_id,
        "target_person_embedding": emb_list,
        "use_enhancer": use_enhancer,
        "use_smoothing": use_smoothing,
        "use_grain": use_grain,
        "iteration": 1,
        "fidelity": 0.92,
        "color_strength": 0.15,
        "sharpen_amount": 0.15
    }

    thread = threading.Thread(
        target=run_video_swap_job,
        args=(job_id, src_paths if len(src_paths) > 1 else primary_src, tgt_path, chunk_duration, start_offset, part_number, target_person_id, emb_list, use_enhancer, use_smoothing, use_grain, 0.92, 0.15, 0.15),
        daemon=True
    )
    thread.start()

    return {
        "job_id": job_id,
        "type": "video",
        "iteration": 1,
        "part_number": part_number,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "total_video_duration": total_video_duration,
        "has_more_parts": has_more_parts,
        "next_start_offset": next_start_offset,
        "num_sources": len(src_paths),
        "status": "queued",
        "message": f"Part {part_number} ({int(start_offset)}s - {int(end_offset)}s) face swap started!"
    }

class MergeVideoPartsRequest(BaseModel):
    job_ids: Optional[List[str]] = None
    filenames: Optional[List[str]] = None

@app.post("/api/merge-video-parts")
async def merge_video_parts(req: MergeVideoPartsRequest):
    """
    Merges multiple processed video parts (Part 1, Part 2, etc.) into 1 continuous final video.
    """
    input_files = []
    if req.job_ids:
        for jid in req.job_ids:
            if jid in jobs and jobs[jid].get("status") == JobStatus.COMPLETED:
                p = jobs[jid].get("output_path")
                if p and os.path.exists(p):
                    input_files.append(p)
            else:
                out_path = os.path.join(OUTPUT_DIR, f"swapped_{jid}.mp4")
                if os.path.exists(out_path):
                    input_files.append(out_path)
    elif req.filenames:
        for fn in req.filenames:
            p = os.path.join(OUTPUT_DIR, fn)
            if os.path.exists(p):
                input_files.append(p)
                
    if len(input_files) < 2:
        raise HTTPException(status_code=400, detail="At least 2 completed video parts are required to merge.")

    merge_id = str(uuid.uuid4())[:8]
    merged_filename = f"merged_{merge_id}.mp4"
    merged_output_path = os.path.join(OUTPUT_DIR, merged_filename)

    engine = FaceSwapEngine.get_instance()
    try:
        engine.merge_video_files(input_files, merged_output_path)
        return {
            "status": "completed",
            "merge_id": merge_id,
            "parts_merged": len(input_files),
            "merged_url": f"/outputs/{merged_filename}",
            "download_url": f"/api/download/{merged_filename}",
            "message": f"Successfully merged {len(input_files)} video parts into 1 complete video!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


@app.post("/api/regenerate")
async def regenerate_swap(req: RegenerateRequest):
    """
    Regenerates previous photo/video face swap with customized AI hyperparameter tuning
    based on user satisfaction feedback (e.g. Max Likeness, Ultra-HD, Ambient Glow, Auto-Improve).
    """
    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Previous job not found. Please upload fresh media.")
    
    prev_job = jobs[req.job_id]
    raw_src = prev_job.get("source_paths") or prev_job.get("source_path")
    src_paths = []
    def _collect_paths(val):
        if isinstance(val, str) and os.path.exists(val):
            src_paths.append(val)
        elif isinstance(val, (list, tuple)):
            for v in val:
                _collect_paths(v)
    _collect_paths(raw_src)

    tgt_path = prev_job.get("target_path")
    
    if not src_paths or not tgt_path or not isinstance(tgt_path, str) or not os.path.exists(tgt_path):
        raise HTTPException(status_code=400, detail="Original source or target files are no longer available. Please upload fresh media.")
        
    src_path = src_paths if len(src_paths) > 1 else src_paths[0]
        
    new_job_id = str(uuid.uuid4())[:8]
    job_type = prev_job.get("type", "photo")
    prev_iteration = prev_job.get("iteration", 1)
    new_iteration = prev_iteration + 1
    
    preset = req.tuning_preset or "auto_improve"
    use_enhancer = prev_job.get("use_enhancer", True) if req.use_enhancer is None else req.use_enhancer
    use_grain = prev_job.get("use_grain", True) if req.use_grain is None else req.use_grain
    use_smoothing = prev_job.get("use_smoothing", True) if req.use_smoothing is None else req.use_smoothing

    if preset == "max_likeness":
        # 100% Pure Input Face Copy: 100% source identity, zero lighting shift, natural skin
        use_enhancer = True
        use_grain = False
        fidelity = 1.0
        color_strength = 0.0
        sharpen_amount = 0.12
        preset_title = "100% Pure Input Face Copy (Exact Identity Match)"
    elif preset == "ultra_hd":
        # Ultra-HD: Maximum GFPGAN pore restoration & intense crisp eye sharpening
        use_enhancer = True
        use_grain = True
        fidelity = 0.88
        color_strength = 0.15
        sharpen_amount = 0.52
        preset_title = "Ultra-HD & Sharp Eyes (Max GFPGAN Detail)"
    elif preset == "ambient_blend":
        # Cinematic Ambient Blend: Deep scene lighting harmonization & soft shadow integration
        use_enhancer = True
        use_grain = True
        fidelity = 0.78
        color_strength = 0.55
        sharpen_amount = 0.0
        preset_title = "Cinematic Ambient Lighting & Seamless Blend"
    elif preset == "auto_improve":
        # Smart AI Improvement
        use_enhancer = True
        use_grain = True
        fidelity = min(0.96, 0.88 + (new_iteration - 1) * 0.04)
        color_strength = max(0.15, 0.25 - (new_iteration - 1) * 0.03)
        sharpen_amount = min(0.35, 0.20 + (new_iteration - 1) * 0.05)
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
        "source_path": src_paths[0],
        "source_paths": src_paths,
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

# ==========================================
# WEBRTC VIDEO CALL SIGNALING & LIVE SWAP
# ==========================================

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, client_id: str, websocket: WebSocket):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
        self.rooms[room_id][client_id] = websocket
        
        # Notify other peers in the room
        await self.broadcast_to_room(room_id, {
            "type": "user-joined",
            "client_id": client_id,
            "participants": list(self.rooms[room_id].keys())
        }, exclude_client=client_id)
        
        # Send current participants list to the new user
        await websocket.send_json({
            "type": "room-info",
            "room_id": room_id,
            "client_id": client_id,
            "participants": list(self.rooms[room_id].keys())
        })

    async def disconnect(self, room_id: str, client_id: str):
        if room_id in self.rooms and client_id in self.rooms[room_id]:
            del self.rooms[room_id][client_id]
            if not self.rooms[room_id]:
                del self.rooms[room_id]
            else:
                await self.broadcast_to_room(room_id, {
                    "type": "user-left",
                    "client_id": client_id,
                    "participants": list(self.rooms[room_id].keys())
                })

    async def send_to_peer(self, room_id: str, target_client_id: str, message: dict):
        if room_id in self.rooms and target_client_id in self.rooms[room_id]:
            try:
                await self.rooms[room_id][target_client_id].send_json(message)
            except Exception as e:
                print(f"[RoomManager] Error sending to peer {target_client_id}: {e}")

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_client: Optional[str] = None):
        if room_id in self.rooms:
            for cid, ws in list(self.rooms[room_id].items()):
                if exclude_client and cid == exclude_client:
                    continue
                try:
                    await ws.send_json(message)
                except Exception as e:
                    print(f"[RoomManager] Error broadcasting to {cid}: {e}")

room_manager = RoomManager()

@app.post("/api/live/set-source")
async def set_live_source(
    source_files: Optional[List[UploadFile]] = File(None),
    preset_name: Optional[str] = Form(None)
):
    """Registers and pre-computes 3D face identity embedding for real-time live webcam and video calling."""
    engine = FaceSwapEngine.get_instance()
    if not engine.is_initialized:
        engine.initialize()

    source_id = f"src_{uuid.uuid4().hex[:8]}"
    try:
        if preset_name:
            preset_path = os.path.join(SAMPLES_DIR, preset_name)
            if not os.path.exists(preset_path):
                raise HTTPException(status_code=404, detail="Preset image not found")
            engine.register_live_source(source_id, [preset_path])
        elif source_files:
            bytes_list = []
            for sf in source_files:
                content = await sf.read()
                if len(content) > 0:
                    bytes_list.append(content)
            if not bytes_list:
                raise HTTPException(status_code=400, detail="Empty source files")
            engine.register_live_source_from_bytes(source_id, bytes_list)
        else:
            raise HTTPException(status_code=400, detail="No source file or preset provided")

        return {"status": "success", "source_id": source_id, "message": "Live face identity initialized"}
    except Exception as e:
        print(f"[LiveSource] Error setting live source: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class VirtualCamStartRequest(BaseModel):
    width: Optional[int] = 640
    height: Optional[int] = 480
    fps: Optional[int] = 25

@app.get("/api/virtualcam/status")
def get_virtualcam_status():
    """Check availability and status of system virtual camera (OBS/DirectShow)."""
    manager = VirtualCamManager.get_instance()
    return manager.check_availability()

@app.post("/api/virtualcam/start")
def start_virtualcam(req: VirtualCamStartRequest = VirtualCamStartRequest()):
    """Start feeding swapped frames into the virtual camera."""
    manager = VirtualCamManager.get_instance()
    try:
        res = manager.start(width=req.width, height=req.height, fps=req.fps)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/virtualcam/stop")
def stop_virtualcam():
    """Stop the virtual camera stream."""
    manager = VirtualCamManager.get_instance()
    res = manager.stop()
    return {"status": "success", "data": res}

@app.websocket("/ws/live-swap")
async def websocket_live_swap(websocket: WebSocket):
    """Real-time webcam streaming face swap endpoint with optional Virtual Camera feed."""
    await websocket.accept()
    engine = FaceSwapEngine.get_instance()
    vcam_manager = VirtualCamManager.get_instance()

    if not engine.is_initialized:
        try:
            engine.initialize()
        except Exception as e:
            print(f"[WebSocket Live] Engine init error: {e}")

    try:
        while True:
            data = await websocket.receive_json()
            t_start = time.time()
            
            frame_b64 = data.get("frame")
            source_id = data.get("source_id")
            fast_mode = data.get("fast_mode", True)
            use_enhancer = data.get("use_enhancer", False)
            color_strength = float(data.get("color_strength", 0.25))
            send_to_vcam = data.get("send_to_vcam", False)

            if not frame_b64:
                continue

            if "," in frame_b64:
                frame_b64 = frame_b64.split(",", 1)[1]
            
            img_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame_bgr is None:
                await websocket.send_json({"error": "Failed to decode frame", "detected": False})
                continue

            swapped_bgr, detected = engine.swap_frame_live(
                frame_bgr,
                source_id=source_id,
                use_enhancer=use_enhancer,
                color_strength=color_strength,
                fast_mode=fast_mode
            )

            # If virtual camera is active or requested, push frame
            if vcam_manager.is_active or send_to_vcam:
                vcam_manager.push_frame(swapped_bgr)

            # JPEG compress for fast network transfer
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80 if fast_mode else 90]
            _, buffer = cv2.imencode('.jpg', swapped_bgr, encode_param)
            out_b64 = base64.b64encode(buffer).decode('utf-8')
            
            latency_ms = round((time.time() - t_start) * 1000, 1)

            await websocket.send_json({
                "frame": f"data:image/jpeg;base64,{out_b64}",
                "detected": detected,
                "latency_ms": latency_ms,
                "vcam_active": vcam_manager.is_active
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket Live] Error: {e}")


@app.websocket("/ws/video-call/{room_id}/{client_id}")
async def websocket_video_call(websocket: WebSocket, room_id: str, client_id: str):
    """WebRTC video call signaling hub (supports peer-to-peer audio/video streaming)."""
    await room_manager.connect(room_id, client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            target_client = data.get("target")
            
            data["sender"] = client_id
            data["room_id"] = room_id

            if target_client:
                await room_manager.send_to_peer(room_id, target_client, data)
            else:
                await room_manager.broadcast_to_room(room_id, data, exclude_client=client_id)

    except WebSocketDisconnect:
        await room_manager.disconnect(room_id, client_id)
    except Exception as e:
        print(f"[WebRTC Call] Error in room {room_id} for client {client_id}: {e}")
        await room_manager.disconnect(room_id, client_id)

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

