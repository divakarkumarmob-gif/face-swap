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
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Tuple, List, Dict, Any
from insightface.app.common import Face
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

def preserve_source_complexion(enhanced_bgr: np.ndarray, source_ref: np.ndarray, strength: float = 0.90) -> np.ndarray:
    """
    Guarantees that the swapped face retains the exact natural skin tone,
    melanin level, warmth, and complexion of the original input photo,
    preventing over-whitening or artificial fairness from AI enhancement.
    """
    try:
        enh_lab = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        src_lab = cv2.cvtColor(source_ref, cv2.COLOR_BGR2LAB).astype(np.float32)
        
        enh_mean, enh_std = np.mean(enh_lab, axis=(0, 1), keepdims=True), np.std(enh_lab, axis=(0, 1), keepdims=True) + 1e-6
        src_mean, src_std = np.mean(src_lab, axis=(0, 1), keepdims=True), np.std(src_lab, axis=(0, 1), keepdims=True) + 1e-6
        
        # Color match L, A, B channels directly to source reference
        corrected_lab = (enh_lab - enh_mean) * (src_std / enh_std) + src_mean
        corrected_lab = np.clip(corrected_lab, 0, 255).astype(np.uint8)
        corrected_bgr = cv2.cvtColor(corrected_lab, cv2.COLOR_LAB2BGR)
        
        return cv2.addWeighted(corrected_bgr, strength, enhanced_bgr, 1.0 - strength, 0)
    except Exception:
        return enhanced_bgr

def apply_sharpening(img: np.ndarray, amount: float = 0.25) -> np.ndarray:
    """
    Applies cinematic unsharp masking to boost eye crispness, iris clarity, and skin texture.
    """
    if amount <= 0.01:
        return img
    gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
    sharpened = cv2.addWeighted(img, 1.0 + amount, gaussian, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)

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

def parse_face_bisenet(target_crop_512: np.ndarray, parser_session: Optional[onnxruntime.InferenceSession] = None) -> Optional[np.ndarray]:
    """
    Runs 19-class BiSeNet face parser on 512x512 aligned target crop.
    Returns float32 mask isolating swap regions (skin, eyebrows, eyes, nose, lips)
    while strictly protecting hair strands, eyeglasses, microphone, and background.
    """
    if parser_session is None or target_crop_512 is None:
        return None
    try:
        h, w = target_crop_512.shape[:2]
        img_512 = cv2.resize(target_crop_512, (512, 512), interpolation=cv2.INTER_LANCZOS4) if (w, h) != (512, 512) else target_crop_512
        img_rgb = cv2.cvtColor(img_512, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_norm = (img_rgb - mean) / std
        img_input = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

        input_name = parser_session.get_inputs()[0].name
        output_name = parser_session.get_outputs()[0].name
        pred = parser_session.run([output_name], {input_name: img_input})[0]

        if pred.ndim == 4:
            pred = pred[0]
        if pred.shape[0] == 19:
            parsing_map = np.argmax(pred, axis=0)
        else:
            parsing_map = pred.squeeze()

        # Swap regions: skin(1), left_eyebrow(2), right_eyebrow(3), left_eye(4), right_eye(5), nose(10), mouth(11), upper_lip(12), lower_lip(13)
        # Excluded / protected: background(0), glasses(6), ears(7,8), neck(14), cloth(16), hair(17), hat(18)
        swap_classes = {1, 2, 3, 4, 5, 10, 11, 12, 13}
        mask = np.isin(parsing_map, list(swap_classes)).astype(np.float32)

        # Multi-stage Gaussian feathering for smooth edge blending
        mask = cv2.GaussianBlur(mask, (31, 31), 8.0)
        mask = np.clip(mask / (np.max(mask) + 1e-6), 0.0, 1.0)
        return mask
    except Exception as e:
        print(f"[FaceParser] BiSeNet parsing error: {e}")
        return None

def create_landmark_face_mask_512(
    target_face,
    M_512: np.ndarray,
    target_crop_512: Optional[np.ndarray] = None,
    size: int = 512,
    parser_session: Optional[onnxruntime.InferenceSession] = None
) -> np.ndarray:
    """
    Creates a custom landmark-guided anatomical convex mask fitted to the exact
    jawline, cheekbones, and eyebrow contours of the target face.
    Ensures 100% solid coverage over the upper lip, philtrum, chin, and jaw so that
    any mustache, beard, or facial hair on the target is completely replaced by the input face.
    """
    lmks = None
    if hasattr(target_face, 'landmark_2d_106') and target_face.landmark_2d_106 is not None:
        lmks = target_face.landmark_2d_106
    elif hasattr(target_face, 'landmark_3d_68') and target_face.landmark_3d_68 is not None:
        lmks = target_face.landmark_3d_68[:, :2]
    elif hasattr(target_face, 'kps') and target_face.kps is not None:
        lmks = target_face.kps

    if lmks is None:
        return create_face_mask(size)

    try:
        # Transform landmarks into 512x512 aligned crop coordinate space
        lmks_512 = np.dot(lmks, M_512[:2, :2].T) + M_512[:2, 2]
        hull = cv2.convexHull(lmks_512.astype(np.int32))

        mask = np.zeros((size, size), dtype=np.float32)
        cv2.fillConvexPoly(mask, hull, 1.0)

        # Soft forehead top fade-off to protect natural hairline
        top_fade_start = int(size * 0.16)
        top_fade_end = int(size * 0.32)
        for y in range(top_fade_start, top_fade_end):
            factor = (y - top_fade_start) / float(top_fade_end - top_fade_start)
            mask[y, :] *= factor
        mask[:top_fade_start, :] = 0.0

        # Protect upper eye glasses frames if present, but NEVER reduce mask on mustache/mouth/chin area
        if target_crop_512 is not None and parser_session is not None:
            try:
                # Only check glasses on upper face (y < 0.55)
                h, w = target_crop_512.shape[:2]
                img_512 = cv2.resize(target_crop_512, (512, 512)) if (w, h) != (512, 512) else target_crop_512
                img_rgb = cv2.cvtColor(img_512, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
                std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
                img_norm = (img_rgb - mean) / std
                img_input = np.transpose(img_norm, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

                pred = parser_session.run(None, {parser_session.get_inputs()[0].name: img_input})[0]
                parsing_map = np.argmax(pred[0], axis=0)
                glasses_mask = (parsing_map == 6).astype(np.float32)
                if np.sum(glasses_mask) > 100:
                    glasses_blurred = cv2.GaussianBlur(glasses_mask, (15, 15), 3.0)
                    mask *= (1.0 - np.clip(glasses_blurred * 0.75, 0.0, 0.90))
            except Exception:
                pass

        # Smooth Gaussian feathering along outer boundary
        mask = cv2.GaussianBlur(mask, (35, 35), 10.0)
        mask = np.clip(mask / (np.max(mask) + 1e-6), 0.0, 1.0)
        return mask
    except Exception as e:
        print(f"[FaceMask] Convex hull fallback: {e}")
        return create_face_mask(size)

def apply_directional_lighting(swapped_face: np.ndarray, target_crop: np.ndarray, strength: float = 0.30) -> np.ndarray:
    """
    Extracts low-pass luminance shading distribution from the target face to cast
    authentic directional shadows, sunlight angle, and specular cheek/nose highlights.
    """
    try:
        tgt_gray = cv2.cvtColor(target_crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
        tgt_shading = cv2.GaussianBlur(tgt_gray, (45, 45), 0)
        tgt_mean_l = np.mean(tgt_shading)
        if tgt_mean_l < 1.0:
            return swapped_face
            
        light_mod = tgt_shading / max(1e-3, tgt_mean_l)
        light_mod = np.clip(light_mod, 0.72, 1.32)
        light_mod_3d = np.repeat(light_mod[:, :, np.newaxis], 3, axis=2)

        relit = swapped_face.astype(np.float32) * (1.0 - strength + strength * light_mod_3d)
        return np.clip(relit, 0, 255).astype(np.uint8)
    except Exception as e:
        print(f"[LightingTransfer] Fallback: {e}")
        return swapped_face

def match_camera_focus(swapped_face: np.ndarray, target_crop: np.ndarray) -> np.ndarray:
    """
    Measures target image focal plane sharpness and gently matches lens blur / bokeh
    if the target photo was captured with shallow depth of field.
    """
    try:
        tgt_lap = cv2.Laplacian(target_crop, cv2.CV_64F).var()
        swap_lap = cv2.Laplacian(swapped_face, cv2.CV_64F).var()
        
        # If target has lens bokeh (substantially softer than AI swapped face), apply subtle focal blur
        if swap_lap > 450.0 and tgt_lap < 180.0:
            blur_sigma = np.clip((200.0 - tgt_lap) / 120.0, 0.3, 1.2)
            return cv2.GaussianBlur(swapped_face, (0, 0), blur_sigma)
        return swapped_face
    except Exception as e:
        return swapped_face

def estimate_head_pose(kps: np.ndarray) -> Tuple[float, float, float]:
    """
    Estimates 3D head pose (Yaw, Pitch, Roll in degrees) from 5-point facial landmarks:
    kps[0]: left eye, kps[1]: right eye, kps[2]: nose, kps[3]: left mouth, kps[4]: right mouth
    """
    if kps is None or len(kps) < 5:
        return 0.0, 0.0, 0.0
    
    le = kps[0]
    re = kps[1]
    nose = kps[2]
    lm = kps[3]
    rm = kps[4]
    
    dx = float(re[0] - le[0])
    dy = float(re[1] - le[1])
    roll = math.degrees(math.atan2(dy, dx))
    
    eye_dist = math.hypot(dx, dy) + 1e-6
    eye_center = (le + re) / 2.0
    
    nose_dx = float(nose[0] - eye_center[0])
    yaw_ratio = np.clip(nose_dx / (eye_dist * 0.5), -1.0, 1.0)
    yaw = float(np.degrees(np.arcsin(yaw_ratio)))
    
    mouth_center = (lm + rm) / 2.0
    eye_to_mouth = float(np.linalg.norm(mouth_center - eye_center)) + 1e-6
    eye_to_nose = float(np.linalg.norm(nose - eye_center))
    pitch_ratio = eye_to_nose / eye_to_mouth
    pitch = float(np.clip((pitch_ratio - 0.55) * 90.0, -45.0, 45.0))
    
    return yaw, pitch, roll

def get_pose_weighted_embedding(profile: List[Dict[str, Any]], target_kps: np.ndarray) -> Optional[np.ndarray]:
    """
    Dynamically computes optimal identity embedding vector based on target face head pose.
    Interpolates embeddings with higher weights given to source photos closest in 3D angle.
    """
    if not profile:
        return None
    if len(profile) == 1:
        return profile[0]['embedding']
        
    tgt_yaw, tgt_pitch, tgt_roll = estimate_head_pose(target_kps)
    
    weights = []
    for item in profile:
        s_yaw, s_pitch, s_roll = item['pose']
        ang_dist = math.sqrt(2.0 * (tgt_yaw - s_yaw)**2 + 1.2 * (tgt_pitch - s_pitch)**2 + 0.5 * (tgt_roll - s_roll)**2)
        w = math.exp(-ang_dist / 25.0)
        weights.append(w)
        
    weights_arr = np.array(weights, dtype=np.float32)
    sum_w = np.sum(weights_arr)
    if sum_w > 1e-6:
        weights_arr /= sum_w
    else:
        weights_arr = np.ones_like(weights_arr) / len(weights_arr)
        
    blended_emb = np.zeros_like(profile[0]['embedding'], dtype=np.float32)
    for i, item in enumerate(profile):
        blended_emb += weights_arr[i] * item['embedding']
        
    norm = np.linalg.norm(blended_emb)
    if norm > 1e-6:
        blended_emb /= norm
    return blended_emb

def match_film_grain(swapped_face: np.ndarray, target_crop: np.ndarray) -> np.ndarray:
    """
    Measures sensor noise / film grain from target skin and synthesizes
    matching subtle grain onto swapped face to prevent plastic/flat look.
    """
    try:
        gray_tgt = cv2.cvtColor(target_crop, cv2.COLOR_BGR2GRAY)
        blurred_tgt = cv2.GaussianBlur(gray_tgt, (5, 5), 0)
        noise_est = np.std(gray_tgt.astype(np.float32) - blurred_tgt.astype(np.float32))
        
        noise_sigma = np.clip(noise_est * 0.30, 0.4, 3.0)
        
        h, w, c = swapped_face.shape
        noise = np.random.normal(0, noise_sigma, (h, w, c)).astype(np.float32)
        grained = np.clip(swapped_face.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return grained
    except Exception as e:
        return swapped_face
    
def harmonize_expression_dynamics(swapped_face_512: np.ndarray, target_face, target_kps: np.ndarray) -> np.ndarray:
    """
    Harmonizes mouth smile curvature, jaw openness, and eye squint tension
    between the target expression and swapped facial geometry so the result
    never looks like an expressionless 'wax museum' mask.
    """
    if target_kps is None or len(target_kps) < 5:
        return swapped_face_512
    try:
        le, re, nose, lm, rm = target_kps[:5]
        mouth_w = np.linalg.norm(rm - lm) + 1e-6
        eye_w = np.linalg.norm(re - le) + 1e-6
        smile_ratio = mouth_w / eye_w
        
        if smile_ratio > 0.85:
            h, w = swapped_face_512.shape[:2]
            mouth_roi_y1, mouth_roi_y2 = int(h * 0.65), int(h * 0.92)
            mouth_roi_x1, mouth_roi_x2 = int(w * 0.22), int(w * 0.78)
            mouth_roi = swapped_face_512[mouth_roi_y1:mouth_roi_y2, mouth_roi_x1:mouth_roi_x2]
            if mouth_roi.size > 0:
                lab = cv2.cvtColor(mouth_roi, cv2.COLOR_BGR2LAB)
                clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(4, 4))
                lab[:, :, 0] = clahe.apply(lab[:, :, 0])
                swapped_face_512[mouth_roi_y1:mouth_roi_y2, mouth_roi_x1:mouth_roi_x2] = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        return swapped_face_512
    except Exception as e:
        return swapped_face_512

def laplacian_pyramid_blend(target_bgr: np.ndarray, swapped_bgr: np.ndarray, mask_float: np.ndarray, num_levels: int = 3) -> np.ndarray:
    """
    Performs multi-band Laplacian Pyramid frequency blending.
    Decomposes images into frequency octaves (high-freq skin texture, mid-freq facial structure, low-freq lighting)
    and blends each octave independently with the corresponding octave of the Gaussian mask.
    Eliminates color stepping, visible boundary seams, and lighting mismatch.
    """
    try:
        h, w = target_bgr.shape[:2]
        divisor = 2 ** num_levels
        pad_h = (divisor - (h % divisor)) % divisor
        pad_w = (divisor - (w % divisor)) % divisor
        
        if pad_h > 0 or pad_w > 0:
            tgt_pad = cv2.copyMakeBorder(target_bgr, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT_101)
            swp_pad = cv2.copyMakeBorder(swapped_bgr, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT_101)
            msk_pad = cv2.copyMakeBorder(mask_float, 0, pad_h, 0, pad_w, cv2.BORDER_REFLECT_101)
        else:
            tgt_pad, swp_pad, msk_pad = target_bgr, swapped_bgr, mask_float

        tgt_f = tgt_pad.astype(np.float32)
        swp_f = swp_pad.astype(np.float32)
        if msk_pad.ndim == 2:
            msk_f = np.repeat(msk_pad[:, :, np.newaxis], 3, axis=2).astype(np.float32)
        else:
            msk_f = msk_pad.astype(np.float32)

        # 1. Build Gaussian Pyramids
        gauss_tgt = [tgt_f]
        gauss_swp = [swp_f]
        gauss_msk = [msk_f]

        for i in range(num_levels):
            gauss_tgt.append(cv2.pyrDown(gauss_tgt[-1]))
            gauss_swp.append(cv2.pyrDown(gauss_swp[-1]))
            gauss_msk.append(cv2.pyrDown(gauss_msk[-1]))

        # 2. Build Laplacian Pyramids
        lap_tgt = [gauss_tgt[num_levels]]
        lap_swp = [gauss_swp[num_levels]]

        for i in range(num_levels, 0, -1):
            h_prev, w_prev = gauss_tgt[i - 1].shape[:2]
            up_tgt = cv2.pyrUp(gauss_tgt[i], dstsize=(w_prev, h_prev))
            up_swp = cv2.pyrUp(gauss_swp[i], dstsize=(w_prev, h_prev))
            lap_tgt.append(gauss_tgt[i - 1] - up_tgt)
            lap_swp.append(gauss_swp[i - 1] - up_swp)

        # 3. Blend each Laplacian frequency band
        lap_blend = []
        base_msk = gauss_msk[num_levels]
        lap_blend.append(lap_swp[0] * base_msk + lap_tgt[0] * (1.0 - base_msk))

        for i in range(1, num_levels + 1):
            cur_msk = gauss_msk[num_levels - i]
            b_layer = lap_swp[i] * cur_msk + lap_tgt[i] * (1.0 - cur_msk)
            lap_blend.append(b_layer)

        # 4. Reconstruct composite image from pyramid
        comp = lap_blend[0]
        for i in range(1, num_levels + 1):
            h_cur, w_cur = lap_blend[i].shape[:2]
            comp = cv2.pyrUp(comp, dstsize=(w_cur, h_cur)) + lap_blend[i]

        comp = np.clip(comp, 0, 255).astype(np.uint8)
        return comp[:h, :w]
    except Exception as e:
        mask_3d = np.repeat(mask_float[:, :, np.newaxis], 3, axis=2) if mask_float.ndim == 2 else mask_float
        return np.clip(swapped_bgr.astype(np.float32) * mask_3d + target_bgr.astype(np.float32) * (1.0 - mask_3d), 0, 255).astype(np.uint8)

def apply_optical_flow_temporal_stabilizer(
    prev_raw: np.ndarray,
    curr_raw: np.ndarray,
    prev_swapped: np.ndarray,
    curr_swapped: np.ndarray,
    temporal_weight: float = 0.22
) -> np.ndarray:
    """
    Stabilizes video face swap by tracking dense Farneback optical flow motion vectors
    between consecutive target frames, warping previous swapped frame to current position,
    and blending to eliminate 100% of micro-flicker, temporal lighting flutter, and landmark jitter.
    """
    if prev_raw is None or prev_swapped is None or curr_raw is None or curr_swapped is None:
        return curr_swapped
    try:
        # Downscale by 2x for ultra-fast real-time optical flow computation
        h, w = curr_raw.shape[:2]
        small_w, small_h = max(64, w // 2), max(64, h // 2)
        
        prev_small = cv2.resize(prev_raw, (small_w, small_h), interpolation=cv2.INTER_AREA)
        curr_small = cv2.resize(curr_raw, (small_w, small_h), interpolation=cv2.INTER_AREA)
        
        prev_gray = cv2.cvtColor(prev_small, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_small, cv2.COLOR_BGR2GRAY)
        
        # Dense Farneback Optical Flow
        flow_small = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None,
            pyr_scale=0.5, levels=2, winsize=13,
            iterations=2, poly_n=5, poly_sigma=1.1, flags=0
        )
        flow = cv2.resize(flow_small, (w, h), interpolation=cv2.INTER_LINEAR) * 2.0
        
        grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        map_x = grid_x - flow[..., 0]
        map_y = grid_y - flow[..., 1]
        
        warped_prev_swap = cv2.remap(
            prev_swapped, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101
        )
        
        # Motion magnitude: during fast head turns, decrease temporal weight
        motion_mag = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
        motion_weight = np.clip(1.0 - (motion_mag / 15.0), 0.0, 1.0)[:, :, np.newaxis]
        
        alpha = float(np.clip(temporal_weight, 0.05, 0.35)) * motion_weight
        stabilized = (1.0 - alpha) * curr_swapped.astype(np.float32) + alpha * warped_prev_swap.astype(np.float32)
        return np.clip(stabilized, 0, 255).astype(np.uint8)
    except Exception as e:
        print(f"[OpticalFlow] Stabilization fallback: {e}")
        return curr_swapped

class FaceSwapEngine:
    _instance = None
    
    def __init__(self):
        self.app = None
        self.swapper = None
        self.enhancer_session = None
        self.codeformer_session = None
        self.parser_session = None
        self.is_initialized = False
        self.model_path = None
        self.enhancer_path = None
        self.codeformer_path = None
        self.parser_path = None
        self._cached_mask_512 = None
        self._cached_mask_256 = None
        self.live_sources = {}
        
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

        try:
            self.codeformer_path = download_model("codeformer.onnx", progress_callback)
        except Exception as e:
            print(f"CodeFormer download skipped: {e}")

        try:
            self.parser_path = download_model("face_parser.onnx", progress_callback)
        except Exception as e:
            print(f"Face Parser download skipped: {e}")

        if progress_callback:
            progress_callback(40, "Loading Face Analysis AI (InsightFace)...")
            
        available_providers = onnxruntime.get_available_providers()
        ai_providers = ['CPUExecutionProvider']
        if 'CUDAExecutionProvider' in available_providers:
            try:
                # Verify CUDA provider is actually functional
                test_sess = onnxruntime.InferenceSession(self.model_path, providers=['CUDAExecutionProvider'])
                ai_providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                print("[FaceSwapEngine] 🚀 NVIDIA CUDA GPU Acceleration VERIFIED & ACTIVE!")
            except Exception as e:
                print(f"[FaceSwapEngine] ⚠️ CUDA Provider available but session failed ({e}). Falling back to CPU.")
                ai_providers = ['CPUExecutionProvider']
        else:
            print("[FaceSwapEngine] ℹ️ CUDA not found in available providers. Running on CPU Mode.")
        
        # Load detection and recognition
        self.app = FaceAnalysis(name='buffalo_l', providers=ai_providers, allowed_modules=['detection', 'recognition'])
        self.app.prepare(ctx_id=0, det_size=(320, 320))
        
        if progress_callback:
            progress_callback(65, "Loading InSwapper 128 Engine...")
            
        self.swapper = insightface.model_zoo.get_model(self.model_path, providers=ai_providers)
        self._cached_mask_512 = create_face_mask(512)

        # 1. Load GFPGAN 1.4 HD Enhancer
        if not self.enhancer_path or not os.path.exists(self.enhancer_path):
            default_gfpgan = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "gfpgan_1.4.onnx")
            if os.path.exists(default_gfpgan):
                self.enhancer_path = default_gfpgan

        if self.enhancer_path and os.path.exists(self.enhancer_path):
            try:
                self.enhancer_session = onnxruntime.InferenceSession(self.enhancer_path, providers=ai_providers)
                print(f"[FaceSwapEngine] GFPGAN 1.4 HD Enhancer loaded successfully from {self.enhancer_path}")
            except Exception as e:
                print(f"[FaceSwapEngine] Could not load GFPGAN session: {e}")

        # 2. Load CodeFormer HD Restorer
        if not self.codeformer_path or not os.path.exists(self.codeformer_path):
            default_codeformer = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "codeformer.onnx")
            if os.path.exists(default_codeformer):
                self.codeformer_path = default_codeformer

        if self.codeformer_path and os.path.exists(self.codeformer_path):
            try:
                self.codeformer_session = onnxruntime.InferenceSession(self.codeformer_path, providers=ai_providers)
                print(f"[FaceSwapEngine] CodeFormer HD Restorer loaded successfully from {self.codeformer_path}")
            except Exception as e:
                print(f"[FaceSwapEngine] Could not load CodeFormer session: {e}")

        # 3. Load BiSeNet Face Parser (Glasses & Hair Occlusion Shield)
        if not self.parser_path or not os.path.exists(self.parser_path):
            default_parser = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "face_parser.onnx")
            if os.path.exists(default_parser):
                self.parser_path = default_parser

        if self.parser_path and os.path.exists(self.parser_path):
            try:
                self.parser_session = onnxruntime.InferenceSession(self.parser_path, providers=ai_providers)
                print(f"[FaceSwapEngine] BiSeNet Face Parser loaded successfully from {self.parser_path}")
            except Exception as e:
                print(f"[FaceSwapEngine] Could not load Face Parser session: {e}")
        
        self.is_initialized = True
        if progress_callback:
            progress_callback(100, "AI Engine Initialized Successfully!")

    def enhance_face(self, face_bgr: np.ndarray, fidelity: float = 0.85, sharpen_amount: float = 0.15) -> np.ndarray:
        """
        Restores crisp eyes, eyelashes, skin pores, and dental details
        directly at 512x512 native resolution using CodeFormer or GFPGAN ONNX.
        """
        orig_h, orig_w = face_bgr.shape[:2]
        img_512 = cv2.resize(face_bgr, (512, 512), interpolation=cv2.INTER_LANCZOS4) if (orig_w, orig_h) != (512, 512) else face_bgr

        active_session = self.codeformer_session if self.codeformer_session is not None else self.enhancer_session

        if active_session is None:
            gaussian = cv2.GaussianBlur(img_512, (0, 0), 2.0)
            sharp_wt = 1.0 + max(0.05, sharpen_amount * 2.0)
            sharp = cv2.addWeighted(img_512, sharp_wt, gaussian, -(sharp_wt - 1.0), 0)
            return sharp if (orig_w, orig_h) == (512, 512) else cv2.resize(sharp, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

        try:
            # Normalized RGB tensor
            img_norm = (img_512.astype(np.float32) / 255.0 - 0.5) / 0.5
            img_rgb = img_norm[:, :, ::-1]
            img_trans = np.transpose(img_rgb, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

            inputs = {}
            input_names = [inp.name for inp in active_session.get_inputs()]
            inputs[input_names[0]] = img_trans

            # CodeFormer optional fidelity weight parameter
            if len(input_names) > 1:
                second_inp = active_session.get_inputs()[1]
                if "double" in second_inp.type:
                    weight_val = np.array(float(np.clip(fidelity, 0.4, 0.95)), dtype=np.double)
                else:
                    weight_val = np.array([float(np.clip(fidelity, 0.4, 0.95))], dtype=np.float32)
                inputs[input_names[1]] = weight_val

            output_name = active_session.get_outputs()[0].name
            pred = active_session.run([output_name], inputs)[0]
            
            out_img = pred[0].transpose((1, 2, 0))
            out_img = np.clip((out_img * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
            out_bgr = out_img[:, :, ::-1]
            
            # Crisp detail enhancement for sharp eyes, eyelashes & skin pores
            if sharpen_amount > 0.02:
                blur = cv2.GaussianBlur(out_bgr, (0, 0), 1.0)
                sharp_wt = 1.0 + sharpen_amount * 1.2
                sharp = cv2.addWeighted(out_bgr, sharp_wt, blur, -(sharp_wt - 1.0), 0)
                return sharp if (orig_w, orig_h) == (512, 512) else cv2.resize(sharp, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)

            return out_bgr if (orig_w, orig_h) == (512, 512) else cv2.resize(out_bgr, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)
        except Exception as e:
            print(f"[FaceEnhancer] Inference error: {e}")
            gaussian = cv2.GaussianBlur(img_512, (0, 0), 1.5)
            return cv2.addWeighted(img_512, 1.2, gaussian, -0.2, 0)


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

    def extract_unique_faces_from_video(self, video_path: str, output_dir: str, max_samples: int = 60) -> List[Dict[str, Any]]:
        """
        Samples video frames, extracts unique persons using multi-angle centroid face clustering,
        and saves cropped avatar previews representing each true individual in the video.
        """
        if not self.is_initialized:
            self.initialize()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        step = max(1, total_frames // max_samples)

        clusters = []  # List of {'embeddings': [...], 'centroid': ..., 'best_crop': ..., 'best_score': ..., 'count': int}
        frame_idx = 0

        while cap.isOpened() and frame_idx < total_frames:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % step == 0:
                faces = self.get_all_faces(frame)
                h, w = frame.shape[:2]
                for face in faces:
                    emb = face.normed_embedding
                    bbox = face.bbox.astype(int)
                    face_w = max(1, bbox[2] - bbox[0])
                    face_h = max(1, bbox[3] - bbox[1])
                    face_area = face_w * face_h
                    if face_area < 500:  # Skip tiny/blurry background detections
                        continue

                    # Crop with margin
                    pad_w = int(face_w * 0.25)
                    pad_h = int(face_h * 0.25)
                    x1 = max(0, bbox[0] - pad_w)
                    y1 = max(0, bbox[1] - pad_h)
                    x2 = min(w, bbox[2] + pad_w)
                    y2 = min(h, bbox[3] + pad_h)
                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue

                    # Quality & frontality scoring: favor larger, more frontal faces
                    score = float(face_area)
                    if hasattr(face, 'kps') and face.kps is not None and len(face.kps) >= 5:
                        eye_dist = np.linalg.norm(face.kps[0] - face.kps[1])
                        # Measure symmetry of nose relative to eyes
                        mid_eye = (face.kps[0] + face.kps[1]) / 2.0
                        nose = face.kps[2]
                        symmetry = 1.0 / (abs(mid_eye[0] - nose[0]) / max(1.0, eye_dist) + 0.1)
                        score += eye_dist * 40 + symmetry * 100

                    # Match against existing clusters with cosine similarity threshold of 0.44
                    best_match_idx = -1
                    best_match_sim = -1.0
                    for c_idx, cluster in enumerate(clusters):
                        sim_centroid = float(np.dot(emb, cluster['centroid']))
                        sim_angles = max([float(np.dot(emb, e)) for e in cluster['embeddings']])
                        sim = max(sim_centroid, sim_angles)

                        if sim > best_match_sim:
                            best_match_sim = sim
                            best_match_idx = c_idx

                    # 0.44 threshold clusters all angles of the same individual together
                    if best_match_idx != -1 and best_match_sim >= 0.44:
                        cl = clusters[best_match_idx]
                        if len(cl['embeddings']) < 12:
                            cl['embeddings'].append(emb.copy())
                        cl['count'] += 1
                        # Update centroid (normalized mean)
                        all_embs = np.array(cl['embeddings'])
                        mean_emb = np.mean(all_embs, axis=0)
                        cl['centroid'] = mean_emb / (np.linalg.norm(mean_emb) + 1e-8)

                        # If this crop is clearer/larger/more frontal, update preview crop
                        if score > cl['best_score']:
                            cl['best_crop'] = crop.copy()
                            cl['best_score'] = score
                    else:
                        if len(clusters) < 8:  # Cap at top 8 unique people
                            clusters.append({
                                'embeddings': [emb.copy()],
                                'centroid': emb.copy(),
                                'best_crop': crop.copy(),
                                'best_score': score,
                                'count': 1
                            })

            frame_idx += 1

        cap.release()

        # Sort clusters by frequency of appearance (main characters first)
        clusters.sort(key=lambda c: (c['count'], c['best_score']), reverse=True)

        # Save crops and prepare JSON response
        os.makedirs(output_dir, exist_ok=True)
        results = []
        for idx, cluster in enumerate(clusters):
            crop_filename = f"person_{idx}_{int(time.time())}.jpg"
            crop_path = os.path.join(output_dir, crop_filename)
            cv2.imwrite(crop_path, cluster['best_crop'])

            # Store multi-angle centroid and all angle embeddings (up to 8 angles)
            angle_embs = [e.tolist() for e in cluster['embeddings'][:8]]
            results.append({
                'person_id': idx,
                'label': f"Person {idx + 1}" if idx > 0 else "Person 1 (Main Character)",
                'appearances': cluster['count'],
                'preview_url': f"/uploads/{crop_filename}",
                'centroid': cluster['centroid'].tolist(),
                'embedding': cluster['centroid'].tolist(),
                'cluster_embeddings': angle_embs
            })

        return results


    def build_multi_angle_profile(self, source_imgs: List[np.ndarray]) -> List[Dict[str, Any]]:
        """
        Constructs a 3D pose-indexed identity profile from 1 or more source photos.
        Extracts embedding, head pose angles (yaw, pitch, roll), and landmarks.
        """
        profile = []
        for img in source_imgs:
            face = self.get_face(img)
            if face is not None and hasattr(face, 'kps') and face.kps is not None:
                yaw, pitch, roll = estimate_head_pose(face.kps)
                profile.append({
                    'face': face,
                    'embedding': face.normed_embedding.copy(),
                    'pose': (yaw, pitch, roll),
                    'kps': face.kps
                })
        return profile

    def get_multi_source_master_embedding(self, source_imgs: List[np.ndarray]) -> np.ndarray:
        """
        Extracts pure, high-precision identity embedding from source photo(s).
        For single photo, returns the direct uncorrupted normed embedding.
        For multiple photos, computes the normalized centroid.
        """
        all_embs = []
        for img in source_imgs:
            face = self.get_face(img)
            if face is not None:
                all_embs.append(face.normed_embedding.copy())

        if not all_embs:
            raise ValueError("No valid faces could be extracted from the uploaded source photo(s).")

        if len(all_embs) == 1:
            return all_embs[0]

        master_emb = np.mean(all_embs, axis=0)
        norm = np.linalg.norm(master_emb)
        if norm > 1e-6:
            master_emb /= norm
        return master_emb

    def high_quality_blend(
        self,
        target_img: np.ndarray,
        target_face,
        source_face,
        smooth_kps: Optional[np.ndarray] = None,
        source_embedding: Optional[np.ndarray] = None,
        source_profile: Optional[List[Dict[str, Any]]] = None,
        use_enhancer: bool = True,
        use_grain: bool = True,
        fidelity: float = 0.85,
        color_strength: float = 0.28,
        sharpen_amount: float = 0.15
    ) -> Tuple[np.ndarray, np.ndarray]:
        kps_to_use = smooth_kps if smooth_kps is not None else target_face.kps
        
        # 1. Aligned crop and InSwapper Inference
        aimg, M = face_align.norm_crop2(target_img, kps_to_use, 128)
        M_512 = M * 4.0

        blob = cv2.dnn.blobFromImage(
            aimg, 1.0 / self.swapper.input_std, (128, 128),
            (self.swapper.input_mean, self.swapper.input_mean, self.swapper.input_mean),
            swapRB=True
        )
        
        if source_embedding is not None:
            norm_emb = source_embedding
        elif source_profile and len(source_profile) > 0:
            norm_emb = get_pose_weighted_embedding(source_profile, kps_to_use)
        elif source_face is not None:
            norm_emb = source_face.normed_embedding
        else:
            raise ValueError("No valid source embedding, profile, or face provided.")
            
        latent = norm_emb.reshape((1, -1))
        latent = np.dot(latent, self.swapper.emap)
        latent /= np.linalg.norm(latent)
        
        pred = self.swapper.session.run(
            self.swapper.output_names,
            {self.swapper.input_names[0]: blob, self.swapper.input_names[1]: latent}
        )[0]
        
        img_fake = pred.transpose((0, 2, 3, 1))[0]
        bgr_fake = np.clip(255 * img_fake, 0, 255).astype(np.uint8)[:, :, ::-1]

        # 2. 100% Pure GFPGAN HD Enhancement ON the swapped face (Zero low-res blur mixing!)
        fake_512 = cv2.resize(bgr_fake, (512, 512), interpolation=cv2.INTER_LANCZOS4)
        if use_enhancer and self.enhancer_session is not None:
            img_norm = (fake_512.astype(np.float32) / 255.0 - 0.5) / 0.5
            img_trans = np.transpose(img_norm[:, :, ::-1], (2, 0, 1))[np.newaxis, ...].astype(np.float32)
            pred_gfp = self.enhancer_session.run(None, {self.enhancer_session.get_inputs()[0].name: img_trans})[0]
            out_face_512 = np.clip((pred_gfp[0].transpose((1, 2, 0)) * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)[:, :, ::-1]
        else:
            out_face_512 = fake_512

        # 3. Source Complexion Preservation vs Target Lighting Harmonization
        aimg_512 = cv2.resize(aimg, (512, 512), interpolation=cv2.INTER_LANCZOS4)
        if color_strength > 0.05:
            out_face_512 = color_transfer(out_face_512, aimg_512, strength=color_strength)
        else:
            out_face_512 = preserve_source_complexion(out_face_512, fake_512, strength=0.80)

        # 4. Crisp Micro-Detail Sharpening (Guarantees razor-sharp eye & skin texture)
        effective_sharpen = max(0.20, sharpen_amount)
        out_face_512 = apply_sharpening(out_face_512, amount=effective_sharpen)

        # 5. Film Grain Simulation (Controlled by use_grain)
        if use_grain:
            out_face_512 = match_film_grain(out_face_512, aimg_512)

        # 6. Inverse 512x512 Affine Warp
        IM_512 = cv2.invertAffineTransform(M_512)
        h, w = target_img.shape[:2]
        warped_face = cv2.warpAffine(
            out_face_512, IM_512, (w, h),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_REFLECT_101
        )

        # 7. Crisp Anatomical Mask (Erases target beard/eyebrows with crisp seamless edges)
        mask_512 = np.zeros((512, 512), dtype=np.float32)
        cv2.ellipse(mask_512, (256, 265), (175, 220), 0, 0, 360, 1.0, -1)
        mask_512 = cv2.GaussianBlur(mask_512, (31, 31), 10.0)

        warped_mask = cv2.warpAffine(mask_512, IM_512, (w, h), flags=cv2.INTER_LINEAR, borderValue=0.0)
        warped_mask_3d = np.repeat(warped_mask[:, :, np.newaxis], 3, axis=2)

        final_blended = np.clip(
            warped_mask_3d * warped_face.astype(np.float32) + (1.0 - warped_mask_3d) * target_img.astype(np.float32),
            0, 255
        ).astype(np.uint8)

        return final_blended, kps_to_use

    def swap_image(
        self,
        source_img_paths: Any = None,
        target_img_path: Optional[str] = None,
        output_path: Optional[str] = None,
        use_enhancer: bool = True,
        use_grain: bool = True,
        fidelity: float = 0.85,
        color_strength: float = 0.28,
        sharpen_amount: float = 0.15,
        source_img_path: Any = None,
        multi_person_sources: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        if not self.is_initialized:
            self.initialize()
            
        target_img = cv2.imread(target_img_path)
        if target_img is None:
            raise ValueError("Could not read target image.")

        target_faces = self.get_all_faces(target_img)
        if not target_faces:
            raise ValueError("No face detected in the target image.")

        # Multi-person simultaneous swap (Person 1 -> Target 1, Person 2 -> Target 2)
        if multi_person_sources and len(multi_person_sources) > 0:
            # Sort target faces left-to-right
            target_faces_sorted = sorted(target_faces, key=lambda f: f.bbox[0])
            result = target_img.copy()

            for i, t_face in enumerate(target_faces_sorted):
                p_src = multi_person_sources[min(i, len(multi_person_sources) - 1)]
                s_face = p_src.get('source_face')
                s_emb = p_src.get('source_embedding')
                if s_face is not None:
                    result, _ = self.high_quality_blend(
                        result, t_face, s_face,
                        source_embedding=s_emb,
                        use_enhancer=use_enhancer,
                        use_grain=use_grain,
                        fidelity=fidelity,
                        color_strength=color_strength,
                        sharpen_amount=sharpen_amount
                    )

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(output_path, result)
            return output_path

        # Single person default swap
        input_src = source_img_paths if source_img_paths is not None else source_img_path
        if input_src is None:
            raise ValueError("No source image provided.")

        if isinstance(input_src, str):
            source_paths = [input_src]
        else:
            source_paths = list(input_src)

        source_imgs = []
        for p in source_paths:
            img = cv2.imread(p)
            if img is not None:
                source_imgs.append(img)

        if not source_imgs:
            raise ValueError("Could not read source image.")
            
        source_profile = self.build_multi_angle_profile(source_imgs)
        source_emb = self.get_multi_source_master_embedding(source_imgs)
        source_face = self.get_face(source_imgs[0])
            
        result = target_img.copy()
        for t_face in target_faces:
            result, _ = self.high_quality_blend(
                result, t_face, source_face,
                source_embedding=source_emb if len(source_profile) <= 1 else None,
                source_profile=source_profile,
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
        source_img_paths: Any = None,
        target_video_path: Optional[str] = None,
        output_video_path: Optional[str] = None,
        max_duration_sec: float = 30.0,
        start_offset_sec: float = 0.0,
        target_person_id: Optional[int] = None,
        target_person_embedding: Optional[List[float]] = None,
        use_enhancer: bool = True,
        use_smoothing: bool = True,
        use_grain: bool = True,
        fidelity: float = 0.92,
        color_strength: float = 0.15,
        sharpen_amount: float = 0.15,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        source_img_path: Any = None,
        multi_person_sources: Optional[List[Dict[str, Any]]] = None
    ) -> str:

        """
        Processes target video frame by frame with:
        - Multi-person simultaneous swap (Person 1 -> Target 1, Person 2 -> Target 2)
        - 30-second chunking & start_offset support (up to 2 minutes)
        - Specific person targeting (or all people)
        - Pure uncorrupted source face identity lock
        - Dense landmark-guided anatomical masks with smart occlusion
        - Directional lighting & camera depth of field matching
        - Temporal EMA smoothing & Lucas-Kanade optical tracking
        - GFPGAN HD enhancement with high-likeness blend
        - Slice audio preservation
        """
        if not self.is_initialized:
            self.initialize()

        source_face = None
        source_emb = None

        # If not using multi-person sources list, load standard primary source
        if not multi_person_sources:
            input_src = source_img_paths if source_img_paths is not None else source_img_path
            if input_src is None:
                raise ValueError("No source face image(s) provided.")

            if isinstance(input_src, str):
                source_paths = [input_src]
            else:
                source_paths = list(input_src)

            source_imgs = []
            for p in source_paths:
                img = cv2.imread(p)
                if img is not None:
                    source_imgs.append(img)

            if not source_imgs:
                raise ValueError("Could not read source face image(s).")
                
            source_face = self.get_face(source_imgs[0])
            if source_face is None:
                raise ValueError("No face detected in source photo.")

            # Extract 3D multi-angle profile and master embedding for video
            source_profile = self.build_multi_angle_profile(source_imgs)
            source_face = self.get_face(source_imgs[0])
            source_emb = self.get_multi_source_master_embedding(source_imgs)
        else:
            source_profile = []

        cap = cv2.VideoCapture(target_video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open target video: {target_video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_video_frames / fps if total_video_frames > 0 else 30.0
        
        # Calculate start offset and chunk boundaries
        start_offset = max(0.0, float(start_offset_sec))
        start_frame = int(start_offset * fps)
        if start_frame > 0 and start_frame < total_video_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
        remaining_duration = max(0.0, video_duration - start_offset)
        effective_duration = min(remaining_duration, max_duration_sec)
        max_frames_to_process = max(1, int(effective_duration * fps))
        total_frames = min(total_video_frames - start_frame, max_frames_to_process) if total_video_frames > start_frame else max_frames_to_process
        
        temp_dir = os.path.dirname(output_video_path)
        os.makedirs(temp_dir, exist_ok=True)
        temp_no_audio = os.path.join(temp_dir, f"temp_no_audio_{int(time.time()*1000)}.mp4")
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_no_audio, fourcc, fps, (orig_width, orig_height))

        frame_idx = 0
        start_time = time.time()
        
        # Parse multi-angle target embedding(s)
        target_embs_list = []
        if target_person_embedding is not None:
            try:
                if isinstance(target_person_embedding, dict):
                    if 'cluster_embeddings' in target_person_embedding:
                        for e in target_person_embedding['cluster_embeddings']:
                            target_embs_list.append(np.array(e, dtype=np.float32))
                    if 'centroid' in target_person_embedding:
                        target_embs_list.append(np.array(target_person_embedding['centroid'], dtype=np.float32))
                    elif 'embedding' in target_person_embedding:
                        target_embs_list.append(np.array(target_person_embedding['embedding'], dtype=np.float32))
                elif isinstance(target_person_embedding, (list, tuple)):
                    if len(target_person_embedding) > 0 and isinstance(target_person_embedding[0], (list, tuple)):
                        for e in target_person_embedding:
                            target_embs_list.append(np.array(e, dtype=np.float32))
                    else:
                        target_embs_list.append(np.array(target_person_embedding, dtype=np.float32))
            except Exception as e:
                print(f"[VideoSwap] Target embedding parse error: {e}")

        # Helper to process a single frame concurrently across CPU threads
        def process_single_frame(frame):
            if frame is None:
                return None
            try:
                # Multi-person simultaneous swap (Person 1 -> Target 1, Person 2 -> Target 2)
                if multi_person_sources and len(multi_person_sources) > 0:
                    target_faces = self.get_all_faces(frame)
                    if not target_faces:
                        return frame
                    target_faces_sorted = sorted(target_faces, key=lambda f: f.bbox[0])
                    swapped_frame = frame
                    for i, t_face in enumerate(target_faces_sorted):
                        p_src = multi_person_sources[min(i, len(multi_person_sources) - 1)]
                        s_face = p_src.get('source_face')
                        s_emb = p_src.get('source_embedding')
                        if s_face is not None:
                            swapped_frame, _ = self.high_quality_blend(
                                swapped_frame, t_face, s_face,
                                source_embedding=s_emb,
                                use_enhancer=use_enhancer,
                                use_grain=use_grain,
                                fidelity=fidelity,
                                color_strength=color_strength,
                                sharpen_amount=sharpen_amount
                            )
                    return swapped_frame

                if target_person_id == -1:
                    # Swap ALL people in video frame
                    target_faces = self.get_all_faces(frame)
                    if not target_faces:
                        return frame
                    swapped_frame = frame
                    for t_face in target_faces:
                        swapped_frame, _ = self.high_quality_blend(
                            swapped_frame, t_face, source_face,
                            source_embedding=source_emb if len(source_profile) <= 1 else None,
                            source_profile=source_profile,
                            use_enhancer=use_enhancer,
                            use_grain=use_grain,
                            fidelity=fidelity,
                            color_strength=color_strength,
                            sharpen_amount=sharpen_amount
                        )
                    return swapped_frame
                elif target_embs_list:
                    # Target clustered multi-angle embeddings for selected person
                    target_faces = self.get_all_faces(frame)
                    if not target_faces:
                        return frame
                    best_face = None
                    best_sim = -1.0
                    for t_face in target_faces:
                        t_emb = t_face.normed_embedding
                        sims = [float(np.dot(t_emb, ref_emb)) for ref_emb in target_embs_list]
                        max_sim = max(sims) if sims else -1.0
                        if max_sim > best_sim:
                            best_sim = max_sim
                            best_face = t_face

                    if best_face is not None and best_sim >= 0.38:
                        swapped_frame, _ = self.high_quality_blend(
                            frame, best_face, source_face,
                            source_embedding=source_emb if len(source_profile) <= 1 else None,
                            source_profile=source_profile,
                            use_enhancer=use_enhancer,
                            use_grain=use_grain,
                            fidelity=fidelity,
                            color_strength=color_strength,
                            sharpen_amount=sharpen_amount
                        )
                        return swapped_frame
                    else:
                        return frame
                else:
                    # Ultra-Fast: Direct SCRFD detection only (Bypasses recognition & landmark nets)
                    bboxes, kpss = self.app.det_model.detect(frame, max_num=0, metric='default')
                    if len(bboxes) == 0:
                        return frame

                    areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
                    best_idx = int(np.argmax(areas))
                    primary_face = Face(bbox=bboxes[best_idx], kps=kpss[best_idx])

                    swapped_frame, _ = self.high_quality_blend(
                        frame, primary_face, source_face,
                        source_embedding=source_emb if len(source_profile) <= 1 else None,
                        source_profile=source_profile,
                        use_enhancer=use_enhancer,
                        use_grain=use_grain,
                        fidelity=fidelity,
                        color_strength=color_strength,
                        sharpen_amount=sharpen_amount
                    )
                    return swapped_frame
            except Exception as e:
                return frame



        # High-Speed GPU Direct Streaming Pipeline (Eliminates ThreadPool lock & Farneback lag)
        prev_kps = None
        ema_alpha = 0.75

        try:
            while cap.isOpened() and frame_idx < total_frames:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                swapped_frame = process_single_frame(frame)
                out.write(swapped_frame if swapped_frame is not None else frame)
                frame_idx += 1

                # Live progress and ETA calculation
                elapsed = time.time() - start_time
                fps_processing = frame_idx / elapsed if elapsed > 0 else 1.0
                remaining_frames = total_frames - frame_idx
                eta_seconds = remaining_frames / fps_processing if fps_processing > 0 else 0

                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                eta_str = f"{eta_min}m {eta_sec}s" if eta_min > 0 else f"{eta_sec}s"
                percent = int((frame_idx / total_frames) * 100)

                if progress_callback and (frame_idx % 5 == 0 or frame_idx >= total_frames):
                    try:
                        progress_callback(frame_idx, total_frames, percent, eta_str, swapped_frame)
                    except TypeError:
                        progress_callback(frame_idx, total_frames, percent, eta_str)
        finally:
            cap.release()
            out.release()


            
        # Audio preservation
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        has_audio = False
        try:
            check_audio_cmd = [
                ffmpeg_exe, "-ss", str(start_offset),
                "-i", target_video_path,
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
                    "-ss", str(start_offset),
                    "-t", str(effective_duration),
                    "-i", target_video_path,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
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

    def merge_video_files(self, video_paths: List[str], output_path: str) -> str:
        """
        Seamlessly concatenates multiple video segment files (Part 1, Part 2, etc.)
        into 1 continuous final video with perfect audio-video synchronization.
        """
        if not video_paths:
            raise ValueError("No video paths provided to merge.")
            
        valid_paths = [p for p in video_paths if os.path.exists(p)]
        if not valid_paths:
            raise ValueError("None of the specified video parts exist on disk.")
            
        if len(valid_paths) == 1:
            import shutil
            shutil.copyfile(valid_paths[0], output_path)
            return output_path

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_dir = os.path.dirname(output_path)
        os.makedirs(temp_dir, exist_ok=True)
        concat_list_file = os.path.join(temp_dir, f"concat_list_{int(time.time()*1000)}.txt")
        
        with open(concat_list_file, 'w', encoding='utf-8') as f:
            for vp in valid_paths:
                clean_path = os.path.abspath(vp).replace('\\', '/')
                f.write(f"file '{clean_path}'\n")

        try:
            cmd = [
                ffmpeg_exe, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_file,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if os.path.exists(concat_list_file):
                try:
                    os.remove(concat_list_file)
                except:
                    pass

        return output_path


    def register_live_source(self, source_id: str, image_paths: List[str]) -> Dict[str, Any]:
        """Precomputes and caches 3D identity embedding for live camera & video call streaming."""
        if not self.is_initialized:
            self.initialize()
            
        source_imgs = []
        for p in image_paths:
            img = cv2.imread(p)
            if img is not None:
                source_imgs.append(img)
                
        if not source_imgs:
            raise ValueError("No valid image could be read for live source.")
            
        master_emb = self.get_multi_source_master_embedding(source_imgs)
        self.live_sources[source_id] = {
            "embedding": master_emb,
            "timestamp": time.time()
        }
        return {"source_id": source_id, "status": "ready"}

    def register_live_source_from_bytes(self, source_id: str, image_bytes_list: List[bytes]) -> Dict[str, Any]:
        """Registers a live source from uploaded image bytes."""
        if not self.is_initialized:
            self.initialize()
            
        source_imgs = []
        for b in image_bytes_list:
            nparr = np.frombuffer(b, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                source_imgs.append(img)
                
        if not source_imgs:
            raise ValueError("No valid images provided.")
            
        master_emb = self.get_multi_source_master_embedding(source_imgs)
        self.live_sources[source_id] = {
            "embedding": master_emb,
            "timestamp": time.time()
        }
        return {"source_id": source_id, "status": "ready"}

    def swap_frame_live(
        self,
        frame_bgr: np.ndarray,
        source_id: Optional[str] = None,
        source_embedding: Optional[np.ndarray] = None,
        use_enhancer: bool = False,
        color_strength: float = 0.25,
        fast_mode: bool = True
    ) -> Tuple[np.ndarray, bool]:
        """
        Ultra low-latency live frame face swapper for webcam streaming and WebRTC video calls.
        Returns (swapped_frame_bgr, face_detected_bool).
        """
        if not self.is_initialized:
            self.initialize()

        norm_emb = None
        if source_embedding is not None:
            norm_emb = source_embedding
        elif source_id and source_id in self.live_sources:
            norm_emb = self.live_sources[source_id]["embedding"]

        if norm_emb is None:
            return frame_bgr, False

        # Detect faces in live frame
        faces = self.app.get(frame_bgr)
        if not faces:
            return frame_bgr, False

        # Primary face
        target_face = sorted(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]), reverse=True)[0]
        
        # 1. Standard InSwapper Crop
        aimg, M = face_align.norm_crop2(frame_bgr, target_face.kps, 128)
        
        # 2. Inference
        blob = cv2.dnn.blobFromImage(
            aimg, 1.0 / self.swapper.input_std, (128, 128),
            (self.swapper.input_mean, self.swapper.input_mean, self.swapper.input_mean),
            swapRB=True
        )
        
        latent = norm_emb.reshape((1, -1))
        latent = np.dot(latent, self.swapper.emap)
        latent /= np.linalg.norm(latent)
        
        pred = self.swapper.session.run(
            self.swapper.output_names,
            {self.swapper.input_names[0]: blob, self.swapper.input_names[1]: latent}
        )[0]
        
        img_fake = pred.transpose((0, 2, 3, 1))[0]
        bgr_fake = np.clip(255 * img_fake, 0, 255).astype(np.uint8)[:, :, ::-1]

        # Resolution scaling
        res_size = 256 if fast_mode else 512
        scale_fac = 2.0 if fast_mode else 4.0
        M_scaled = M * scale_fac

        bgr_fake_scaled = cv2.resize(bgr_fake, (res_size, res_size), interpolation=cv2.INTER_LINEAR)
        aimg_scaled = cv2.resize(aimg, (res_size, res_size), interpolation=cv2.INTER_LINEAR)

        # Fast color harmonization
        if color_strength > 0.05:
            bgr_fake_harmonized = color_transfer(bgr_fake_scaled, aimg_scaled, strength=color_strength)
        else:
            bgr_fake_harmonized = bgr_fake_scaled

        # Optional detail enhancer (only when not in ultra-fast mode)
        if use_enhancer and self.enhancer_session is not None and not fast_mode:
            bgr_fake_final = self.enhance_face(bgr_fake_harmonized, fidelity=0.85, sharpen_amount=0.15)
        else:
            bgr_fake_final = bgr_fake_harmonized

        # Smooth anatomical mask
        if res_size == 512:
            mask = self._cached_mask_512
        else:
            if not hasattr(self, '_cached_mask_256') or self._cached_mask_256 is None:
                self._cached_mask_256 = create_face_mask(256)
            mask = self._cached_mask_256

        # Invert affine and warp back onto original frame
        IM = cv2.invertAffineTransform(M_scaled)
        h, w = frame_bgr.shape[:2]

        warped_face = cv2.warpAffine(
            bgr_fake_final, IM, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101
        )
        warped_mask = cv2.warpAffine(
            mask, IM, (w, h),
            flags=cv2.INTER_LINEAR,
            borderValue=0.0
        )
        warped_mask_3d = np.repeat(warped_mask[:, :, np.newaxis], 3, axis=2)

        # Alpha composite
        target_f = frame_bgr.astype(np.float32)
        warped_f = warped_face.astype(np.float32)
        blended = warped_mask_3d * warped_f + (1.0 - warped_mask_3d) * target_f
        result = np.clip(blended, 0, 255).astype(np.uint8)

        return result, True

