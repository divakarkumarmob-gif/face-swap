import os
import cv2
import json
import numpy as np
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

class FaceDatasetCurator:
    """
    Automated High-Resolution Face Dataset Preprocessor & Curator (Phase 5).
    Ingests raw image directories (FFHQ, CelebA-HQ, custom user datasets),
    aligns to 512x512 resolution, extracts 512-D identity embeddings,
    computes 3D head poses, and generates metadata manifests.
    """
    def __init__(self, output_dir: str = "dataset_processed", target_size: int = 512):
        self.output_dir = output_dir
        self.target_size = target_size
        self.images_dir = os.path.join(output_dir, "images")
        self.embs_dir = os.path.join(output_dir, "embeddings")
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.embs_dir, exist_ok=True)

    def process_single_image(self, img_path: str, engine: Any, item_idx: int) -> Optional[Dict[str, Any]]:
        try:
            img = cv2.imread(img_path)
            if img is None:
                return None

            face = engine.get_face(img)
            if face is None:
                return None

            # 512x512 standard alignment
            from insightface.utils import face_align
            aimg, _ = face_align.norm_crop2(img, face.kps, self.target_size)

            filename = f"face_{item_idx:06d}.jpg"
            save_img_path = os.path.join(self.images_dir, filename)
            cv2.imwrite(save_img_path, aimg)

            emb_filename = f"emb_{item_idx:06d}.npy"
            save_emb_path = os.path.join(self.embs_dir, emb_filename)
            np.save(save_emb_path, face.normed_embedding)

            # Estimate 3D Pose
            from backend.engine.face_swap_engine import estimate_head_pose
            yaw, pitch, roll = estimate_head_pose(face.kps)

            return {
                "id": item_idx,
                "image_path": save_img_path,
                "embedding_path": save_emb_path,
                "pose": {"yaw": yaw, "pitch": pitch, "roll": roll},
                "bbox": face.bbox.tolist(),
                "kps": face.kps.tolist()
            }
        except Exception as e:
            return None

    def curate_directory(self, input_dir: str, engine: Any, max_samples: int = 5000) -> str:
        """
        Scans input directory, runs parallel extraction, and writes dataset_manifest.json.
        """
        valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
        all_files = [
            os.path.join(input_dir, f)
            for f in os.listdir(input_dir)
            if os.path.splitext(f.lower())[1] in valid_exts
        ][:max_samples]

        print(f"[DatasetCurator] Found {len(all_files)} images to curate.")
        manifest_items = []

        for idx, file_path in enumerate(all_files):
            meta = self.process_single_image(file_path, engine, idx)
            if meta is not None:
                manifest_items.append(meta)
            if (idx + 1) % 100 == 0 or idx == len(all_files) - 1:
                print(f"[DatasetCurator] Processed {idx + 1}/{len(all_files)} images ({len(manifest_items)} valid faces).")

        manifest_path = os.path.join(self.output_dir, "dataset_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump({"total_samples": len(manifest_items), "samples": manifest_items}, f, indent=2)

        print(f"[DatasetCurator] Dataset curation complete! Manifest saved to {manifest_path}")
        return manifest_path
