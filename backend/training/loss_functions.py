import numpy as np
from typing import Dict, Any, Optional

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class IdentityLoss:
    """
    Computes cosine similarity distance between source identity embedding and generated face embedding.
    Supports both PyTorch tensors and NumPy arrays.
    """
    def __call__(self, pred_embedding, target_embedding):
        if HAS_TORCH and isinstance(pred_embedding, torch.Tensor):
            pred_norm = F.normalize(pred_embedding, p=2, dim=-1)
            tgt_norm = F.normalize(target_embedding, p=2, dim=-1)
            cos_sim = torch.sum(pred_norm * tgt_norm, dim=-1)
            return torch.mean(1.0 - cos_sim)
        else:
            p = np.asarray(pred_embedding)
            t = np.asarray(target_embedding)
            p_norm = p / (np.linalg.norm(p, axis=-1, keepdims=True) + 1e-8)
            t_norm = t / (np.linalg.norm(t, axis=-1, keepdims=True) + 1e-8)
            cos_sim = np.sum(p_norm * t_norm, axis=-1)
            return float(np.mean(1.0 - cos_sim))

class SSIMLoss:
    """
    Structural Similarity Index (SSIM) Loss to preserve anatomical structural fidelity.
    """
    def __call__(self, img1, img2):
        if HAS_TORCH and isinstance(img1, torch.Tensor):
            mu1 = F.avg_pool2d(img1, 11, stride=1, padding=5)
            mu2 = F.avg_pool2d(img2, 11, stride=1, padding=5)
            sigma1_sq = F.avg_pool2d(img1 * img1, 11, stride=1, padding=5) - mu1.pow(2)
            sigma2_sq = F.avg_pool2d(img2 * img2, 11, stride=1, padding=5) - mu2.pow(2)
            sigma12 = F.avg_pool2d(img1 * img2, 11, stride=1, padding=5) - mu1 * mu2
            c1, c2 = 0.01 ** 2, 0.03 ** 2
            ssim_map = ((2 * mu1 * mu2 + c1) * (2 * sigma12 + c2)) / ((mu1.pow(2) + mu2.pow(2) + c1) * (sigma1_sq + sigma2_sq + c2))
            return torch.mean(1.0 - ssim_map)
        else:
            i1 = np.asarray(img1, dtype=np.float32)
            i2 = np.asarray(img2, dtype=np.float32)
            l1_diff = np.mean(np.abs(i1 - i2))
            return float(l1_diff * 0.1)

class FaceSwapLossSuite:
    """
    Comprehensive Multi-Objective Loss Suite for SOTA Face Swapper training:
    L_total = lambda_id * L_id + lambda_l1 * L_l1 + lambda_ssim * L_ssim + lambda_temp * L_temp
    """
    def __init__(
        self,
        lambda_id: float = 15.0,
        lambda_l1: float = 10.0,
        lambda_ssim: float = 5.0,
        lambda_per: float = 2.5,
        lambda_temp: float = 4.0
    ):
        self.lambda_id = lambda_id
        self.lambda_l1 = lambda_l1
        self.lambda_ssim = lambda_ssim
        self.lambda_per = lambda_per
        self.lambda_temp = lambda_temp

        self.id_loss_fn = IdentityLoss()
        self.ssim_loss_fn = SSIMLoss()

    def __call__(
        self,
        pred_img,
        target_img,
        pred_emb=None,
        source_emb=None,
        mask=None,
        prev_pred_img=None,
        warped_prev_target=None
    ) -> Dict[str, Any]:
        losses = {}

        # 1. Pixel L1 Loss
        if HAS_TORCH and isinstance(pred_img, torch.Tensor):
            if mask is not None:
                l1 = F.l1_loss(pred_img * mask, target_img * mask)
            else:
                l1 = F.l1_loss(pred_img, target_img)
            losses['l1'] = l1 * self.lambda_l1
            losses['ssim'] = self.ssim_loss_fn(pred_img, target_img) * self.lambda_ssim

            if pred_emb is not None and source_emb is not None:
                losses['id'] = self.id_loss_fn(pred_emb, source_emb) * self.lambda_id
            else:
                losses['id'] = torch.tensor(0.0, device=pred_img.device)

            if prev_pred_img is not None and warped_prev_target is not None:
                losses['temporal'] = F.l1_loss(pred_img, warped_prev_target) * self.lambda_temp
            else:
                losses['temporal'] = torch.tensor(0.0, device=pred_img.device)

            losses['total'] = losses['l1'] + losses['ssim'] + losses['id'] + losses['temporal']
        else:
            p = np.asarray(pred_img, dtype=np.float32)
            t = np.asarray(target_img, dtype=np.float32)
            l1 = float(np.mean(np.abs(p - t))) * self.lambda_l1
            ssim = self.ssim_loss_fn(p, t) * self.lambda_ssim
            losses['l1'] = l1
            losses['ssim'] = ssim

            if pred_emb is not None and source_emb is not None:
                losses['id'] = self.id_loss_fn(pred_emb, source_emb) * self.lambda_id
            else:
                losses['id'] = 0.0

            losses['temporal'] = 0.0
            losses['total'] = l1 + ssim + losses['id']

        return losses
