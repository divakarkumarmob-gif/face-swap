import os
import cv2
import numpy as np
import onnxruntime
import insightface
from insightface.app import FaceAnalysis
from insightface.utils import face_align
import imageio
import imageio_ffmpeg
import subprocess
import time
import math
from typing import Callable, Optional, Tuple, List, Dict, Any
from .model_downloader import download_model

def color_transfer(source_face: np.ndarray, target_face: np.ndarray, strength: float = 0.28) -> np.ndarray:
    """
    Harmonizes ambient lighting and skin tone while strictly preserving
    the input person's distinct facial identity, complexion, eye color, and lip shade.
    """
    src_lab = cv2.cvtColor(source_face, cv2.COLOR_BGR2LAB).astype(np.float32)
    tgt_lab = cv2.cvtColor(target_face, cv2.COLOR_BGR2LAB).astype(np.float32)

    h, w = src_lab.shape[:2]
    cy, cx = h // 2, w // 2
    rx, ry = int(w * 0.28), int(h * 0.35)

    # Sample central facial skin to avoid background color bleed
    src_roi = src_lab[max(0, cy - ry):min(h, cy + ry), max(0, cx - rx):min(w, cx + rx)]
    tgt_roi = tgt_lab[max(0, cy - ry):min(h, cy + ry), max(0, cx - rx):min(w, cx + rx)]

    src_mean, src_std = cv2.meanStdDev(src_roi)
    tgt_mean, tgt_std = cv2.meanStdDev(tgt_roi)

    src_mean = src_mean.reshape((1, 1, 3))
    src_std = np.maximum(src_std.reshape((1, 1, 3)), 1e-4)

    tgt_mean = tgt_mean.reshape((1, 1, 3))
    tgt_std = np.maximum(tgt_std.reshape((1, 1, 3)), 1e-4)

    # Lighting & chrominance alignment
    res_lab = (src_lab - src_mean) * (tgt_std / src_std) + tgt_mean
    res_lab = np.clip(res_lab, 0, 255).astype(np.uint8)
    res_bgr = cv2.cvtColor(res_lab, cv2.COLOR_LAB2BGR)

    # Controlled blend: keeps authentic source identity while matching target environment
    return cv2.addWeighted(res_bgr, strength, source_face, 1.0 - strength, 0)

def create_face_mask(size: int = 512) -> np.ndarray:
    """
    Creates a high-resolution 512x512 anatomical facial mask with smooth 
    gradient feathering for seamless blending without harsh borders or double chins.
    """
    mask = np.zeros((size, size), dtype=np.float32)
    center = (int(size * 0.50), int(size * 0.53))
    axes = (int(size * 0.36), int(size * 0.44))

    # Inner anatomical ellipse
    cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)

    # Top forehead soft transition (preserves natural hair bangs/hairline of target)
    top_fade_start = int(size * 0.15)
    top_fade_end = int(size * 0.30)
    for y in range(top_fade_start, top_fade_end):
        factor = (y - top_fade_start) / float(top_fade_end - top_fade_start)
        mask[y, :] *= factor
    mask[:top_fade_start, :] = 0.0

    # Multi-stage Gaussian Blur for cinematic feathering
    mask = cv2.GaussianBlur(mask, (65, 65), 20.0)
    mask = np.clip(mask / (np.max(mask) + 1e-6), 0.0, 1.0)
    return mask

def match_film_grain(swapped_face: np.ndarray, target_crop: np.ndarray) -> np.ndarray:
    """
    Measures sensor noise / film grain from target skin and synthesizes
    matching subtle grain onto swapped face to prevent plastic/flat look.
    """
    gray_tgt = cv2.cvtColor(target_crop, cv2.COLOR_BGR2GRAY)
    blurred_tgt = cv2.GaussianBlur(gray_tgt, (5, 5), 0)
    noise_est = np.std(gray_tgt.astype(np.float32) - blurred_tgt.astype(np.float32))
    
    noise_sigma = np.clip(noise_est * 0.30, 0.4, 3.0)
    
    h, w, c = swapped_face.shape
    noise = np.random.normal(0, noise_sigma, (h, w, c)).astype(np.float32)
    
    grained = swapped_face.astype(np.float32) + noise
    return np.clip(grained, 0, 255).astype(np.uint8)

class FaceSwapEngine:
    _instance = None
    
    def __init__(self):
        self.app = None
        self.swapper = None
        self.enhancer_session = None
        self.is_initialized = False
        self.model_path = None
        self.enhancer_path = None
        self._cached_mask_512 = None
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FaceSwapEngine()
        return cls._instance

    def initialize(self, progress_callback: Optional[Callable[[int, str], None]] = None):
        if self.is_initialized:
            return
        
        if progress_callback:
            progress_callback(5, "Checking AI models...")
            
        self.model_path = download_model("inswapper_128.onnx", progress_callback)
        
        try:
            self.enhancer_path = download_model("gfpgan_1.4.onnx", progress_callback)
        except Exception as e:
            print(f"GFPGAN download skipped: {e}")

        if progress_callback:
            progress_callback(50, "Loading Face Analysis AI (InsightFace)...")
            
        available_providers = onnxruntime.get_available_providers()
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if 'CUDAExecutionProvider' in available_providers else ['CPUExecutionProvider']
        
        self.app = FaceAnalysis(name='buffalo_l', providers=providers)
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
        if progress_callback:
            progress_callback(75, "Loading InSwapper 128 Engine...")
            
        self.swapper = insightface.model_zoo.get_model(self.model_path, providers=providers)
        self._cached_mask_512 = create_face_mask(512)

        if not self.enhancer_path or not os.path.exists(self.enhancer_path):
            default_gfpgan = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "gfpgan_1.4.onnx")
            if os.path.exists(default_gfpgan):
                self.enhancer_path = default_gfpgan

        if self.enhancer_path and os.path.exists(self.enhancer_path):
            try:
                if progress_callback:
                    progress_callback(90, "Loading GFPGAN HD Face Enhancer...")
                self.enhancer_session = onnxruntime.InferenceSession(self.enhancer_path, providers=providers)
                print(f"[FaceSwapEngine] GFPGAN 1.4 HD Enhancer loaded successfully from {self.enhancer_path}")
            except Exception as e:
                print(f"[FaceSwapEngine] Could not load GFPGAN session: {e}")
        else:
            print("[FaceSwapEngine] Warning: GFPGAN 1.4 model file not found on disk.")
        
        self.is_initialized = True
        if progress_callback:
            progress_callback(100, "AI Engine Initialized Successfully!")

    def enhance_face(self, face_bgr: np.ndarray, fidelity: float = 0.85, sharpen_amount: float = 0.15) -> np.ndarray:
        """
        Restores crisp eyes, eyelashes, skin pores, and dental details
        directly at 512x512 native resolution using GFPGAN ONNX.
        """
        orig_h, orig_w = face_bgr.shape[:2]
        img_512 = cv2.resize(face_bgr, (512, 512), interpolation=cv2.INTER_LANCZOS4) if (orig_w, orig_h) != (512, 512) else face_bgr

        if self.enhancer_session is None:
            print("[GFPGAN] Session is None, applying unsharp contrast filter.")
            gaussian = cv2.GaussianBlur(img_512, (0, 0), 2.0)
            sharp_wt = 1.0 + max(0.05, sharpen_amount * 2.0)
            sharp = cv2.addWeighted(img_512, sharp_wt, gaussian, -(sharp_wt - 1.0), 0)
            return sharp if (orig_w, orig_h) == (512, 512) else cv2.resize(sharp, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

        try:
            img_norm = (img_512.astype(np.float32) / 255.0 - 0.5) / 0.5
            img_rgb = img_norm[:, :, ::-1]
            img_trans = np.transpose(img_rgb, (2, 0, 1))[np.newaxis, ...]

            input_name = self.enhancer_session.get_inputs()[0].name
            output_name = self.enhancer_session.get_outputs()[0].name
            
            pred = self.enhancer_session.run([output_name], {input_name: img_trans})[0]
            
            out_img = pred[0].transpose((1, 2, 0))
            out_img = np.clip((out_img * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
            out_bgr = out_img[:, :, ::-1]
            
            # High-fidelity blend with input geometry for authentic source resemblance
            fidelity_clamped = np.clip(fidelity, 0.50, 1.0)
            enhanced = cv2.addWeighted(out_bgr, fidelity_clamped, img_512, 1.0 - fidelity_clamped, 0)
            
            # Unsharp detail enhancement for ultra-photorealistic eyes & lips
            if sharpen_amount > 0.01:
                blur = cv2.GaussianBlur(enhanced, (0, 0), 1.5)
                sharp_wt = 1.0 + sharpen_amount
                sharp = cv2.addWeighted(enhanced, sharp_wt, blur, -sharpen_amount, 0)
                return sharp if (orig_w, orig_h) == (512, 512) else cv2.resize(sharp, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

            return enhanced if (orig_w, orig_h) == (512, 512) else cv2.resize(enhanced, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)
        except Exception as e:
            print(f"[GFPGAN] enhance error: {e}")
            gaussian = cv2.GaussianBlur(img_512, (0, 0), 2.0)
            return cv2.addWeighted(img_512, 1.25, gaussian, -0.25, 0)

    def get_face(self, img_bgr: np.ndarray):
        """Extract primary face from image."""
        if not self.is_initialized:
            self.initialize()
        faces = self.app.get(img_bgr)
        if not faces:
            return None
        return sorted(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]), reverse=True)[0]

    def get_all_faces(self, img_bgr: np.ndarray):
        """Extract all faces from image."""
        if not self.is_initialized:
            self.initialize()
        return self.app.get(img_bgr)

    def extract_unique_faces_from_video(self, video_path: str, output_dir: str, max_samples: int = 40) -> List[Dict[str, Any]]:
        """
        Samples video frames, extracts unique persons using face embedding similarity,
        and saves cropped avatar previews.
        """
        if not self.is_initialized:
            self.initialize()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        step = max(1, total_frames // max_samples)

        unique_people = [] # List of {'embedding': ..., 'crop': ..., 'bbox': ...}
        frame_idx = 0

        while cap.isOpened() and frame_idx < total_frames and len(unique_people) < 8:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % step == 0:
                faces = self.get_all_faces(frame)
                for face in faces:
                    # Check if face already clustered
                    is_known = False
                    for person in unique_people:
                        sim = np.dot(face.normed_embedding, person['embedding'])
                        if sim > 0.60:
                            is_known = True
                            break

                    if not is_known:
                        # Crop face with padding
                        bbox = face.bbox.astype(int)
                        h, w = frame.shape[:2]
                        pad_w = int((bbox[2] - bbox[0]) * 0.25)
                        pad_h = int((bbox[3] - bbox[1]) * 0.25)
                        x1 = max(0, bbox[0] - pad_w)
                        y1 = max(0, bbox[1] - pad_h)
                        x2 = min(w, bbox[2] + pad_w)
                        y2 = min(h, bbox[3] + pad_h)

                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            unique_people.append({
                                'embedding': face.normed_embedding.copy(),
                                'crop': crop.copy(),
                                'face_obj': face
                            })

            frame_idx += 1

        cap.release()

        # Save crops and prepare JSON response
        os.makedirs(output_dir, exist_ok=True)
        results = []
        for idx, person in enumerate(unique_people):
            crop_filename = f"person_{idx}_{int(time.time())}.jpg"
            crop_path = os.path.join(output_dir, crop_filename)
            cv2.imwrite(crop_path, person['crop'])

            results.append({
                'person_id': idx,
                'label': f"Person {idx + 1}",
                'preview_url': f"/uploads/{crop_filename}",
                'embedding': person['embedding'].tolist()
            })

        return results

    def high_quality_blend(
        self,
        target_img: np.ndarray,
        target_face,
        source_face,
        smooth_kps: Optional[np.ndarray] = None,
        use_enhancer: bool = True,
        use_grain: bool = True,
        fidelity: float = 0.85,
        color_strength: float = 0.28,
        sharpen_amount: float = 0.15
    ) -> Tuple[np.ndarray, np.ndarray]:
        kps_to_use = smooth_kps if smooth_kps is not None else target_face.kps
        
        # 1. Aligned crop and Affine Matrix (128x128 standard InSwapper alignment)
        aimg, M = face_align.norm_crop2(target_img, kps_to_use, 128)

        # 2. InSwapper Model Inference
        blob = cv2.dnn.blobFromImage(
            aimg, 1.0 / self.swapper.input_std, (128, 128),
            (self.swapper.input_mean, self.swapper.input_mean, self.swapper.input_mean),
            swapRB=True
        )
        latent = source_face.normed_embedding.reshape((1, -1))
        latent = np.dot(latent, self.swapper.emap)
        latent /= np.linalg.norm(latent)
        
        pred = self.swapper.session.run(
            self.swapper.output_names,
            {self.swapper.input_names[0]: blob, self.swapper.input_names[1]: latent}
        )[0]
        
        img_fake = pred.transpose((0, 2, 3, 1))[0]
        bgr_fake = np.clip(255 * img_fake, 0, 255).astype(np.uint8)[:, :, ::-1]

        # 3. High-Resolution 512x512 Expansion
        bgr_fake_512 = cv2.resize(bgr_fake, (512, 512), interpolation=cv2.INTER_LANCZOS4)
        aimg_512 = cv2.resize(aimg, (512, 512), interpolation=cv2.INTER_LANCZOS4)

        # 4. Realistic Skin & Lighting Harmonization (Preserving Source Face Complexion)
        bgr_fake_harmonized = color_transfer(bgr_fake_512, aimg_512, strength=color_strength)

        # 5. HD 512x512 Face Enhancement (GFPGAN photorealism)
        if use_enhancer:
            bgr_fake_hd = self.enhance_face(bgr_fake_harmonized, fidelity=fidelity, sharpen_amount=sharpen_amount)
        else:
            bgr_fake_hd = bgr_fake_harmonized

        # 6. Sensor Grain / Texture Matching
        if use_grain:
            bgr_fake_hd = match_film_grain(bgr_fake_hd, aimg_512)

        # 7. High-Precision 512x512 Anatomical Alpha Mask
        if self._cached_mask_512 is None:
            self._cached_mask_512 = create_face_mask(512)
        crop_mask_512 = self._cached_mask_512.copy()

        # 8. Scale Affine Matrix directly to 512x512 coordinate space
        M_512 = M * 4.0
        IM_512 = cv2.invertAffineTransform(M_512)
        h, w = target_img.shape[:2]

        warped_face = cv2.warpAffine(
            bgr_fake_hd, IM_512, (w, h),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_REFLECT_101
        )
        
        warped_mask = cv2.warpAffine(
            crop_mask_512, IM_512, (w, h),
            flags=cv2.INTER_LINEAR,
            borderValue=0.0
        )
        
        warped_mask_3d = np.repeat(warped_mask[:, :, np.newaxis], 3, axis=2)

        # 9. Ultra-smooth Alpha Composition at Native Resolution
        target_f = target_img.astype(np.float32)
        warped_f = warped_face.astype(np.float32)
        
        blended = warped_mask_3d * warped_f + (1.0 - warped_mask_3d) * target_f
        return np.clip(blended, 0, 255).astype(np.uint8), kps_to_use

    def swap_image(
        self,
        source_img_path: str,
        target_img_path: str,
        output_path: str,
        use_enhancer: bool = True,
        use_grain: bool = True,
        fidelity: float = 0.85,
        color_strength: float = 0.28,
        sharpen_amount: float = 0.15
    ) -> str:
        if not self.is_initialized:
            self.initialize()
            
        source_img = cv2.imread(source_img_path)
        target_img = cv2.imread(target_img_path)
        
        if source_img is None or target_img is None:
            raise ValueError("Could not read source or target image.")
            
        source_face = self.get_face(source_img)
        if source_face is None:
            raise ValueError("No face detected in the source photo.")
            
        target_faces = self.get_all_faces(target_img)
        if not target_faces:
            raise ValueError("No face detected in the target image.")
            
        result = target_img.copy()
        for t_face in target_faces:
            result, _ = self.high_quality_blend(
                result, t_face, source_face,
                use_enhancer=use_enhancer,
                use_grain=use_grain,
                fidelity=fidelity,
                color_strength=color_strength,
                sharpen_amount=sharpen_amount
            )
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, result)
        return output_path

    def process_video(
        self,
        source_img_path: str,
        target_video_path: str,
        output_video_path: str,
        max_duration_sec: float = 30.0,
        target_person_id: Optional[int] = None,
        target_person_embedding: Optional[List[float]] = None,
        use_enhancer: bool = True,
        use_smoothing: bool = True,
        use_grain: bool = True,
        fidelity: float = 0.85,
        color_strength: float = 0.28,
        sharpen_amount: float = 0.15,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None
    ) -> str:
        """
        Processes target video frame by frame with:
        - Specific person targeting (or all people)
        - Temporal smoothing
        - GFPGAN HD enhancement
        - Audio preservation
        """
        if not self.is_initialized:
            self.initialize()
            
        source_img = cv2.imread(source_img_path)
        if source_img is None:
            raise ValueError("Could not read source face image.")
            
        source_face = self.get_face(source_img)
        if source_face is None:
            raise ValueError("No face detected in source photo.")

        cap = cv2.VideoCapture(target_video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open target video: {target_video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_video_frames / fps
        
        effective_duration = min(video_duration, max_duration_sec)
        max_frames_to_process = int(effective_duration * fps)
        total_frames = min(total_video_frames, max_frames_to_process)
        
        temp_dir = os.path.dirname(output_video_path)
        os.makedirs(temp_dir, exist_ok=True)
        temp_no_audio = os.path.join(temp_dir, f"temp_no_audio_{int(time.time())}.mp4")
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_no_audio, fourcc, fps, (orig_width, orig_height))
        
        frame_idx = 0
        start_time = time.time()
        
        target_emb_np = np.array(target_person_embedding, dtype=np.float32) if target_person_embedding else None
        
        smooth_kps = None
        ema_alpha = 0.70
        
        try:
            while cap.isOpened() and frame_idx < total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                target_faces = self.get_all_faces(frame)
                if target_faces:
                    if target_person_id == -1:
                        # Swap ALL people in video
                        swapped_frame = frame
                        for t_face in target_faces:
                            swapped_frame, _ = self.high_quality_blend(
                                swapped_frame, t_face, source_face,
                                use_enhancer=use_enhancer,
                                use_grain=use_grain,
                                fidelity=fidelity,
                                color_strength=color_strength,
                                sharpen_amount=sharpen_amount
                            )
                    elif target_emb_np is not None:
                        # Specific person targeting by facial embedding cosine similarity
                        best_face = None
                        best_sim = -1.0
                        for t_face in target_faces:
                            sim = float(np.dot(t_face.normed_embedding, target_emb_np))
                            if sim > best_sim:
                                best_sim = sim
                                best_face = t_face

                        if best_face is not None and best_sim > 0.48: # Match found
                            if use_smoothing:
                                if smooth_kps is None:
                                    smooth_kps = best_face.kps.copy().astype(np.float32)
                                else:
                                    dist = np.mean(np.linalg.norm(best_face.kps - smooth_kps, axis=1))
                                    if dist > 50:
                                        smooth_kps = best_face.kps.copy().astype(np.float32)
                                    else:
                                        smooth_kps = ema_alpha * best_face.kps.astype(np.float32) + (1.0 - ema_alpha) * smooth_kps
                            else:
                                smooth_kps = None

                            swapped_frame, _ = self.high_quality_blend(
                                frame, best_face, source_face,
                                smooth_kps=smooth_kps,
                                use_enhancer=use_enhancer,
                                use_grain=use_grain,
                                fidelity=fidelity,
                                color_strength=color_strength,
                                sharpen_amount=sharpen_amount
                            )
                        else:
                            swapped_frame = frame
                    else:
                        # Default: swap largest/primary face
                        primary_face = sorted(target_faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]), reverse=True)[0]
                        if use_smoothing:
                            if smooth_kps is None:
                                smooth_kps = primary_face.kps.copy().astype(np.float32)
                            else:
                                dist = np.mean(np.linalg.norm(primary_face.kps - smooth_kps, axis=1))
                                if dist > 50:
                                    smooth_kps = primary_face.kps.copy().astype(np.float32)
                                else:
                                    smooth_kps = ema_alpha * primary_face.kps.astype(np.float32) + (1.0 - ema_alpha) * smooth_kps
                        else:
                            smooth_kps = None

                        swapped_frame, _ = self.high_quality_blend(
                            frame, primary_face, source_face,
                            smooth_kps=smooth_kps,
                            use_enhancer=use_enhancer,
                            use_grain=use_grain,
                            fidelity=fidelity,
                            color_strength=color_strength,
                            sharpen_amount=sharpen_amount
                        )
                else:
                    swapped_frame = frame
                    smooth_kps = None
                    
                out.write(swapped_frame)
                frame_idx += 1
                
                elapsed = time.time() - start_time
                fps_processing = frame_idx / elapsed if elapsed > 0 else 1.0
                remaining_frames = total_frames - frame_idx
                eta_seconds = remaining_frames / fps_processing if fps_processing > 0 else 0
                
                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                eta_str = f"{eta_min}m {eta_sec}s" if eta_min > 0 else f"{eta_sec}s"
                percent = int((frame_idx / total_frames) * 100)
                
                if progress_callback:
                    progress_callback(frame_idx, total_frames, percent, eta_str)
                    
        finally:
            cap.release()
            out.release()
            
        # Audio preservation
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        has_audio = False
        try:
            check_audio_cmd = [
                ffmpeg_exe, "-i", target_video_path,
                "-t", str(effective_duration),
                "-vn", "-acodec", "copy",
                "-f", "null", "-"
            ]
            res = subprocess.run(check_audio_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                has_audio = True
        except:
            has_audio = False

        if has_audio:
            try:
                remux_cmd = [
                    ffmpeg_exe, "-y",
                    "-i", temp_no_audio,
                    "-i", target_video_path,
                    "-t", str(effective_duration),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-map", "0:v:0",
                    "-map", "1:a:0?",
                    "-shortest",
                    output_video_path
                ]
                subprocess.run(remux_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                simple_cmd = [
                    ffmpeg_exe, "-y",
                    "-i", temp_no_audio,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    output_video_path
                ]
                subprocess.run(simple_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            reencode_cmd = [
                ffmpeg_exe, "-y",
                "-i", temp_no_audio,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                output_video_path
            ]
            subprocess.run(reencode_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
        if os.path.exists(temp_no_audio):
            try:
                os.remove(temp_no_audio)
            except:
                pass
                
        return output_video_path
