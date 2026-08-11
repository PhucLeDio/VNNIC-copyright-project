"""
banner_filter.py  --  YOLO Banner Pre-filter (v1.0.5)

Chay model YOLO banner_detection.pt tren danh sach banner thu thap tu Step 2
TRUOC khi dua vao OCR pipeline.

Luong xu ly:
  1. Load YOLO model (lazy singleton qua model_loader.get_banner_model)
  2. Chay inference tung anh (_frame banners)
  3. Neu model du doan 'betting'    -> GIU lai banner de OCR tiep
  4. Neu model du doan 'nonbetting' -> XOA file khoi disk de giai phong bo nho

Public API:
    from banner_filter import run_banner_filter
    betting_banners, stats = run_banner_filter(ad_banners)
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("banner_filter")

# ======================================================
# CONFIG
# ======================================================

# Nguong confidence de chap nhan du doan "betting"
YOLO_CONF_THRESHOLD: float = 0.25

CLASS_BETTING    = "betting"
CLASS_NONBETTING = "nonbetting"

# Them thu muc model/ vao sys.path de import model_loader
_MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
if _MODEL_DIR not in sys.path:
    sys.path.insert(0, _MODEL_DIR)


# ======================================================
# INTERNAL
# ======================================================

def _classify_banner(model, image_path: str) -> tuple[str, float]:
    """
    Chay inference YOLO cho mot anh.
    Returns (predicted_class, confidence):
        predicted_class: "betting" | "nonbetting" | "error"
    """
    try:
        results = model(image_path, conf=YOLO_CONF_THRESHOLD, verbose=False)
    except Exception as e:
        logger.warning(f"[BannerFilter] YOLO inference loi cho {image_path}: {e}")
        return "error", 0.0

    if not results:
        return CLASS_NONBETTING, 0.0

    result = results[0]
    class_names = result.names  # {0: "betting", 1: "nonbetting"} hoac nguoc lai

    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        # Classification task: dung probs
        if hasattr(result, "probs") and result.probs is not None:
            probs     = result.probs
            top_idx   = int(probs.top1)
            top_conf  = float(probs.top1conf)
            top_class = class_names.get(top_idx, CLASS_NONBETTING).lower()
            return top_class, top_conf
        return CLASS_NONBETTING, 0.0

    # Detection task: lay detection co confidence cao nhat
    best_conf  = 0.0
    best_class = CLASS_NONBETTING
    for box in boxes:
        conf      = float(box.conf[0])
        class_idx = int(box.cls[0])
        cls_name  = class_names.get(class_idx, CLASS_NONBETTING).lower()
        if conf > best_conf:
            best_conf  = conf
            best_class = cls_name

    return best_class, best_conf


# ======================================================
# PUBLIC API
# ======================================================

def run_banner_filter(
    banners: list[dict],
    delete_nonbetting: bool = True,
) -> tuple[list[dict], dict]:
    """
    Loc banner bang YOLO banner_detection.pt.

    Args:
        banners          : list[dict] co local_path hop le (da qua filter _frame).
        delete_nonbetting: neu True, xoa file anh nonbetting khoi disk ngay sau khi loc.

    Returns:
        (betting_banners, stats)
        - betting_banners: list[dict] chi gom banner duoc model phan loai la "betting"
        - stats          : dict tom tat ket qua loc
    """
    if not banners:
        return [], {"total": 0, "betting": 0, "nonbetting": 0, "errors": 0, "deleted": 0}

    from model_loader import get_banner_model

    try:
        model = get_banner_model()
    except Exception as e:
        logger.error(f"[BannerFilter] Khong the load YOLO model: {e}")
        # Neu loi load model, tra ve toan bo banner de khong mat bang chung
        return banners, {
            "total": len(banners), "betting": len(banners),
            "nonbetting": 0, "errors": 1, "deleted": 0,
            "error_msg": str(e),
        }

    betting_banners  = []
    nonbetting_paths = []
    n_betting   = 0
    n_nonbetting = 0
    n_errors    = 0

    logger.info(f"[BannerFilter] Bat dau loc {len(banners)} banner bang YOLO...")
    print(f"[BannerFilter] Dang phan tich {len(banners)} banner bang YOLO...")

    for i, banner in enumerate(banners, 1):
        local_path = banner.get("local_path", "")
        if not local_path or not os.path.isfile(local_path):
            n_nonbetting += 1
            continue

        predicted_class, confidence = _classify_banner(model, local_path)
        fname = os.path.basename(local_path)

        if predicted_class == "error":
            # Inference loi -> giu lai de khong mat bang chung
            n_errors += 1
            betting_banners.append({**banner, "yolo_class": "error", "yolo_conf": 0.0})
            logger.warning(f"[BannerFilter] [{i}/{len(banners)}] Inference loi, giu lai: {fname}")

        elif predicted_class == CLASS_BETTING:
            n_betting += 1
            betting_banners.append(
                {**banner, "yolo_class": CLASS_BETTING, "yolo_conf": round(confidence, 4)}
            )
            logger.info(f"[BannerFilter] [{i}/{len(banners)}] BETTING ({confidence:.1%}): {fname}")

        else:
            n_nonbetting += 1
            if banner.get("frames"):
                # Thêm toàn bộ các frame của ảnh động vào danh sách xóa
                nonbetting_paths.extend(banner["frames"])
            else:
                nonbetting_paths.append(local_path)
            logger.info(f"[BannerFilter] [{i}/{len(banners)}] nonbetting ({confidence:.1%}): {fname}")

    # -- Xoa file nonbetting khoi disk --
    deleted = 0
    if delete_nonbetting:
        for path in nonbetting_paths:
            try:
                os.remove(path)
                deleted += 1
            except OSError as err:
                logger.warning(f"[BannerFilter] Khong the xoa file: {path} -- {err}")

    stats = {
        "total":      len(banners),
        "betting":    n_betting,
        "nonbetting": n_nonbetting,
        "errors":     n_errors,
        "deleted":    deleted,
    }

    print(
        f"[BannerFilter] Ket qua YOLO: "
        f"{n_betting} betting giu lai | "
        f"{n_nonbetting} nonbetting da xoa {deleted} file | "
        f"{n_errors} loi inference"
    )
    logger.info(
        f"[BannerFilter] {n_betting} betting | "
        f"{n_nonbetting} nonbetting (xoa {deleted}) | {n_errors} loi"
    )

    return betting_banners, stats
