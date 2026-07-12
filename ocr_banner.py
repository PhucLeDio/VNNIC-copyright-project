"""
OCR Banner Analysis — 3-Tier Cascade Pipeline
==============================================

Phân tích banner ảnh để phát hiện nội dung cờ bạc/cá độ theo kiến trúc
fail-fast cascade 3 tầng: rẻ → đắt, dễ giải trình → mờ hơn.

Mỗi banner chỉ leo lên tầng tiếp theo khi tầng trước KHÔNG tìm thấy gì:

  Tầng 1 — Exact/normalized keyword match  (nhanh nhất, 100% explainable)
  Tầng 2 — Fuzzy string match (rapidfuzz)  (bắt OCR typo/lỗi chính tả)
  Tầng 3 — Semantic embedding (cosine)     (bắt paraphrase / né từ khóa)

Public API:
    from ocr_banner import run_ocr_pipeline
    results = run_ocr_pipeline(banners, keywords_csv="keywords/Keywords_v1.csv")

Mỗi phần tử trong `results` là 1 dict mô tả kết quả phân tích 1 banner:
    {
        "path"         : str,           # đường dẫn ảnh gốc
        "ocr_raw"      : str,           # text thô từ EasyOCR (join tất cả block)
        "ocr_norm"     : str,           # text sau normalize (lowercase, bỏ dấu)
        "matched"      : bool,          # True nếu có tầng nào match
        "tier_hit"     : int | None,    # 1, 2, 3, hoặc None
        "keyword"      : str | None,    # keyword/seed phrase đã match
        "field"        : str | None,    # lĩnh vực (Cờ bạc, Khiêu dâm, ...)
        "violation_level": int | None,  # mức vi phạm từ CSV
        "score"        : float | None,  # similarity score (T2: 0-100, T3: 0-1)
        "score_type"   : str | None,    # "fuzzy_partial_ratio" | "cosine_similarity"
        "frames_ocr"   : list[str],     # danh sách OCR text từng frame (nếu là GIF)
        "error"        : str | None,    # lỗi nếu có
    }
"""

from __future__ import annotations

import csv
import logging
import os
import re
import unicodedata
from typing import Optional

logger = logging.getLogger("ocr_banner")

# ══════════════════════════════════════════════════════════════
# CONFIG — Ngưỡng điều chỉnh được
# ══════════════════════════════════════════════════════════════

# Tầng 2: Fuzzy match
# rapidfuzz.fuzz.partial_ratio trả về 0–100
# 75 = 75% tương đồng; bắt được OCR typo nhẹ mà không quá nhạy
FUZZY_THRESHOLD: int = 75

# Tầng 1 & 2: Chỉ áp dụng cho keyword đủ dài
# Ngăn từ 1–3 ký tự ("đụ", "jav"...) gây false positive trên text ngẫu nhiên
# Ngoại lệ: keyword là tên riêng (brand) ngắn sẽ được handle bởi exact match context
T1_MIN_KW_LEN: int = 4
FUZZY_MIN_KW_LEN: int = 4  # Alias cho nhất quán

# Tầng 3: Cosine similarity threshold (0–1)
COSINE_THRESHOLD: float = 0.75

# Tầng 3: Embedding model (đa ngữ, hỗ trợ tiếng Việt, ~120MB)
EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

# EasyOCR languages để nhận dạng
OCR_LANGUAGES: list[str] = ["vi", "en"]

# Chỉ lấy keyword có violation_level >= ngưỡng này cho OCR
# (1 = vi phạm rõ ràng; 0 = nghi vấn — bỏ qua để giảm false positive)
OCR_MIN_VIOLATION_LEVEL: int = 1


# ══════════════════════════════════════════════════════════════
# SEED PHRASE BANK — Tầng 3
# Các cụm điển hình lấy từ banner cờ bạc thực tế đã biết.
# So sánh theo nghĩa, không theo ký tự → bắt được cách diễn đạt khác
# như "quy đổi tiền thật" ≈ "đổi thưởng" mà T1/T2 sẽ miss.
# ══════════════════════════════════════════════════════════════

GAMBLING_SEED_PHRASES: list[str] = [
    # ── Hành động nạp/rút/đổi thưởng ──
    "nạp tiền nhận thưởng ngay",
    "đăng ký nhận khuyến mãi",
    "rút tiền nhanh chóng",
    "chơi game đổi tiền thật",
    "quy đổi tiền thưởng",
    "đổi điểm lấy tiền mặt",
    "nạp là có ngay",
    "rút tiền tức thì",
    "hoàn tiền khi thua",
    # ── Kêu gọi vào game ──
    "quay là trúng",
    "nổ hũ liên tục",
    "tỷ lệ thắng cao",
    "link vào không bị chặn",
    "cổng game uy tín hàng đầu",
    "thưởng chào mừng thành viên mới",
    "bonus chào mừng",
    "tặng ngay khi đăng ký",
    "vòng quay miễn phí",
    # ── Cược thể thao ──
    "cược thể thao trực tiếp",
    "kèo bóng đá hôm nay",
    "soi kèo nhà cái",
    "tỷ lệ kèo bóng đá",
    "cược trực tiếp",
    # ── Casino trực tuyến ──
    "casino trực tuyến",
    "đại lý chính thức",
    "app cá độ trên điện thoại",
    "sòng bài online",
    "chơi bài ăn tiền thật",
    # ── Ưu đãi mờ ám (né từ khóa nhưng cùng nghĩa) ──
    "hỗ trợ tài chính khi chơi",
    "tham gia để nhận quà",
    "phần thưởng hàng ngày",
    "quà tặng vip",
    "ưu đãi nạp đầu",
]


# ══════════════════════════════════════════════════════════════
# SECTION 1 — TEXT NORMALIZER
# ══════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa text để so khớp tầng 1 & 2:
      - Lowercase
      - Bỏ dấu tiếng Việt (NFD decompose + strip combining marks)
      - Collapse whitespace
      - Giữ lại ký tự Latin, số, khoảng trắng (bỏ ký tự đặc biệt)

    Ví dụ:
      "Nhà Cái SIN88 🎰" → "nha cai sin88"
      "RiKViP™ ĐĂNG KÝ" → "rikvip dang ky"
    """
    if not text:
        return ""
    text = text.lower()
    # Bỏ dấu tiếng Việt: NFD decompose → xóa combining characters
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    # Bỏ ký tự không phải Latin/số/khoảng trắng (emoji, symbol)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.ASCII)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ══════════════════════════════════════════════════════════════
# SECTION 2 — KEYWORD LOADER
# ══════════════════════════════════════════════════════════════

def load_keywords(csv_path: str) -> list[dict]:
    """
    Đọc Keywords_v1.csv, trả về list dicts:
        {
            "keyword"        : str,   # nguyên gốc từ CSV
            "normalized"     : str,   # đã normalize để so khớp T1/T2
            "field"          : str,   # lĩnh vực (Cờ bạc, Khiêu dâm, ...)
            "violation_level": int,   # 0 hoặc 1
        }

    Chỉ giữ lại keyword có violation_level >= OCR_MIN_VIOLATION_LEVEL
    để tránh false positive với từ ngữ thông thường (Giáo dục, Báo chí...).
    """
    if not os.path.exists(csv_path):
        logger.warning(f"[OCR] Keywords CSV không tìm thấy: {csv_path}")
        return []

    keywords: list[dict] = []
    seen_normalized: set[str] = set()

    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kw_raw = (row.get("keyword") or "").strip()
                field  = (row.get("Lĩnh vực") or row.get("linh_vuc") or "").strip()
                try:
                    level = int((row.get("violation_level") or "0").strip())
                except ValueError:
                    level = 0

                if not kw_raw:
                    continue
                if level < OCR_MIN_VIOLATION_LEVEL:
                    continue

                kw_norm = normalize_text(kw_raw)
                if not kw_norm or kw_norm in seen_normalized:
                    continue

                seen_normalized.add(kw_norm)
                keywords.append({
                    "keyword":         kw_raw,
                    "normalized":      kw_norm,
                    "field":           field,
                    "violation_level": level,
                })

    except Exception as e:
        logger.error(f"[OCR] Lỗi đọc Keywords CSV: {e}")

    logger.info(
        f"[OCR] Đã load {len(keywords)} keyword (violation_level >= {OCR_MIN_VIOLATION_LEVEL}) "
        f"từ {csv_path}"
    )
    return keywords


# ══════════════════════════════════════════════════════════════
# SECTION 4 — OCR RUNNER (EasyOCR)
# ══════════════════════════════════════════════════════════════

def _init_ocr_reader():
    """
    Khởi tạo EasyOCR reader. Lazy-load để không tốn RAM nếu không cần.
    Trả về reader object hoặc None nếu EasyOCR chưa được cài.
    """
    try:
        import easyocr
        logger.info(f"[OCR] Khởi tạo EasyOCR với ngôn ngữ: {OCR_LANGUAGES}")
        # gpu=False để tránh phụ thuộc CUDA; đặt gpu=True nếu có GPU
        reader = easyocr.Reader(OCR_LANGUAGES, gpu=False, verbose=False)
        logger.info("[OCR] EasyOCR reader ready.")
        return reader
    except ImportError:
        logger.error("[OCR] EasyOCR chưa được cài. Chạy: pip install easyocr")
        return None
    except Exception as e:
        logger.error(f"[OCR] Lỗi khởi tạo EasyOCR: {e}")
        return None


def run_ocr(image_path: str, reader) -> str:
    """
    Chạy EasyOCR trên 1 file ảnh.

    Args:
        image_path: Đường dẫn tuyệt đối đến file ảnh.
        reader    : EasyOCR reader object (đã khởi tạo từ trước).

    Returns:
        str: Raw text (join các bounding-box block bằng ' ').
             Chuỗi rỗng nếu lỗi hoặc không đọc được gì.
    """
    if reader is None:
        return ""
    if not image_path or not os.path.exists(image_path):
        logger.debug(f"[OCR] File không tồn tại: {image_path}")
        return ""

    try:
        from PIL import Image
        import numpy as np

        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            img_np = np.array(img_rgb)

        results = reader.readtext(img_np, detail=0, paragraph=False)
        raw_text = " ".join(str(r) for r in results if r)
        logger.debug(f"[OCR] {os.path.basename(image_path)} → '{raw_text[:80]}'")
        return raw_text
    except Exception as e:
        logger.warning(f"[OCR] Lỗi readtext trên {image_path}: {e}")
        return ""


# ══════════════════════════════════════════════════════════════
# SECTION 5 — TẦNG 1: EXACT / NORMALIZED KEYWORD MATCH
# ══════════════════════════════════════════════════════════════

def tier1_exact(normalized_text: str, keywords: list[dict]) -> Optional[dict]:
    """
    Tầng 1 — Exact match sau normalize.

    Kiểm tra: normalized_text có chứa keyword.normalized (substring) không?
    Trả về hit dict ngay khi tìm thấy keyword đầu tiên (fail-fast trong tầng).

    Ưu tiên keyword dài hơn trước để tránh false positive ngắn:
      "nha cai" được tìm trước "nha" — tránh match "nhà" thông thường.

    Returns:
        dict với {keyword, field, violation_level, score=1.0} hoặc None.
    """
    if not normalized_text or not keywords:
        return None

    # Sắp xếp theo độ dài normalized keyword giảm dần (longest first)
    sorted_kws = sorted(keywords, key=lambda k: len(k["normalized"]), reverse=True)

    for kw in sorted_kws:
        kw_norm = kw["normalized"]
        if not kw_norm or len(kw_norm) < T1_MIN_KW_LEN:
            continue
        if kw_norm in normalized_text:
            logger.info(
                f"[OCR-T1] ✓ Exact match: '{kw['keyword']}' "
                f"(field={kw['field']}, level={kw['violation_level']})"
            )
            return {
                "keyword":         kw["keyword"],
                "field":           kw["field"],
                "violation_level": kw["violation_level"],
                "score":           1.0,
                "score_type":      "exact_match",
            }

    return None


# ══════════════════════════════════════════════════════════════
# SECTION 6 — TẦNG 2: FUZZY STRING MATCHING (rapidfuzz)
# ══════════════════════════════════════════════════════════════

def tier2_fuzzy(normalized_text: str, keywords: list[dict]) -> Optional[dict]:
    """
    Tầng 2 — Fuzzy match bằng rapidfuzz.fuzz.partial_ratio.

    `partial_ratio` so khớp keyword (ngắn hơn) với chuỗi con tốt nhất trong text
    — phù hợp khi OCR đọc sai vài ký tự nhưng cấu trúc từ còn gần đúng.

    Ví dụ:
      "RUK VIP" vs keyword "rikvip" → partial_ratio cao vì "ruk vip" gần "rikvip".
      "naoonusa" vs bất kỳ keyword → score thấp → pass qua tầng 3.

    Chỉ áp dụng cho keyword có độ dài >= FUZZY_MIN_KW_LEN để tránh false positive.

    Returns:
        dict với {keyword, field, violation_level, score (0-100), score_type} hoặc None.
    """
    if not normalized_text or not keywords:
        return None

    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("[OCR-T2] rapidfuzz chưa được cài. Bỏ qua tầng 2.")
        return None

    best_hit: Optional[dict] = None
    best_score: float = -1.0

    for kw in keywords:
        kw_norm = kw["normalized"]
        if not kw_norm or len(kw_norm) < FUZZY_MIN_KW_LEN:
            continue

        score = fuzz.partial_ratio(kw_norm, normalized_text)

        if score >= FUZZY_THRESHOLD and score > best_score:
            best_score = score
            best_hit = {
                "keyword":         kw["keyword"],
                "field":           kw["field"],
                "violation_level": kw["violation_level"],
                "score":           float(score),
                "score_type":      "fuzzy_partial_ratio",
            }

    if best_hit:
        logger.info(
            f"[OCR-T2] ✓ Fuzzy match: '{best_hit['keyword']}' "
            f"score={best_hit['score']:.1f}/100 "
            f"(field={best_hit['field']})"
        )

    return best_hit


# ══════════════════════════════════════════════════════════════
# SECTION 7 — TẦNG 3: SEMANTIC EMBEDDING + COSINE SIMILARITY
# ══════════════════════════════════════════════════════════════

def _init_embedding_model():
    """
    Lazy-load SentenceTransformer model.
    Chỉ được gọi khi tầng 1 và 2 đều miss — tránh load ~120MB model không cần thiết.
    Trả về model object hoặc None nếu thư viện chưa cài.
    """
    try:
        from sentence_transformers import SentenceTransformer
        logger.info(f"[OCR-T3] Loading embedding model: {EMBEDDING_MODEL} ...")
        model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("[OCR-T3] Embedding model ready.")
        return model
    except ImportError:
        logger.error(
            "[OCR-T3] sentence-transformers chưa được cài. "
            "Chạy: pip install sentence-transformers"
        )
        return None
    except Exception as e:
        logger.error(f"[OCR-T3] Lỗi load embedding model: {e}")
        return None


def tier3_semantic(
    raw_text: str,
    seed_phrases: list[str],
    model,
) -> Optional[dict]:
    """
    Tầng 3 — Semantic embedding + cosine similarity.

    Encode raw_text thành vector, so sánh với từng seed phrase trong bank.
    Lấy cosine similarity cao nhất; nếu >= COSINE_THRESHOLD → có match.

    Dùng raw_text (không normalize) vì embedding model tự xử lý dấu tiếng Việt.
    So với seed_phrases thay vì keyword đơn lẻ vì câu/cụm dài
    → embedding ổn định và có ngữ nghĩa rõ hơn từ đơn.

    Returns:
        dict với {keyword (seed_phrase matched), score, score_type} hoặc None.
    """
    if not raw_text or not seed_phrases or model is None:
        return None

    try:
        import numpy as np

        # Encode OCR text + toàn bộ seed phrases trong 1 batch
        all_texts = [raw_text] + seed_phrases
        embeddings = model.encode(all_texts, normalize_embeddings=True, show_progress_bar=False)

        text_vec  = embeddings[0]
        seed_vecs = embeddings[1:]

        # Cosine similarity = dot product (vì đã normalize embeddings)
        similarities = np.dot(seed_vecs, text_vec)

        best_idx   = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        best_phrase = seed_phrases[best_idx]

        if best_score >= COSINE_THRESHOLD:
            logger.info(
                f"[OCR-T3] ✓ Semantic match: '{best_phrase}' "
                f"cosine={best_score:.3f}"
            )
            return {
                "keyword":         best_phrase,
                "field":           "Cờ bạc (semantic)",
                "violation_level": 1,
                "score":           best_score,
                "score_type":      "cosine_similarity",
            }
        else:
            logger.debug(
                f"[OCR-T3] Miss — best seed: '{best_phrase}' "
                f"cosine={best_score:.3f} < {COSINE_THRESHOLD}"
            )
            return None

    except Exception as e:
        logger.warning(f"[OCR-T3] Lỗi semantic embedding: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# SECTION 8 — PER-BANNER CASCADE
# ══════════════════════════════════════════════════════════════

def analyze_banner(
    banner: dict,
    keywords: list[dict],
    ocr_reader,
    seed_phrases: list[str] = GAMBLING_SEED_PHRASES,
    embedding_model=None,
) -> dict:
    """
    Chạy full cascade 3 tầng cho 1 banner.

    Logic:
      1. Lấy danh sách đường dẫn ảnh cần OCR (local_path + frames nếu là GIF/WEBP)
      2. Chạy OCR trên tất cả, merge text
      3. Tầng 1 → nếu hit: trả về kết quả ngay (không chạy T2/T3)
      4. Tầng 2 → nếu hit: trả về kết quả ngay (không chạy T3)
      5. Tầng 3 → trả về kết quả dù hit hay miss
      6. Trả về dict kết quả đầy đủ

    Args:
        banner         : 1 phần tử từ evidence["banners"]
        keywords       : list từ load_keywords()
        ocr_reader     : EasyOCR reader (đã init)
        seed_phrases   : Danh sách seed phrases cho T3
        embedding_model: SentenceTransformer model (None = chưa load / không dùng T3)

    Returns:
        dict mô tả kết quả phân tích banner này.
    """
    local_path: Optional[str] = banner.get("local_path")
    frames: list[str]         = banner.get("frames", []) or []
    src_url: str              = banner.get("src_url", "")
    case: str                 = banner.get("case", "")

    # Khung kết quả mặc định
    result: dict = {
        "path":            local_path,
        "src_url":         src_url,
        "case":            case,
        "ocr_raw":         "",
        "ocr_norm":        "",
        "matched":         False,
        "tier_hit":        None,
        "keyword":         None,
        "field":           None,
        "violation_level": None,
        "score":           None,
        "score_type":      None,
        "frames_ocr":      [],
        "error":           None,
    }

    # ── Xác định danh sách ảnh cần OCR ──
    # Ảnh động (GIF/WEBP) đã được tách thành frames[] trong step2.
    # Ưu tiên: frames nếu có, fallback về local_path.
    paths_to_ocr: list[str] = []
    if frames:
        paths_to_ocr = [p for p in frames if p and os.path.exists(p)]
    if not paths_to_ocr and local_path and os.path.exists(local_path):
        paths_to_ocr = [local_path]

    if not paths_to_ocr:
        result["error"] = "Không có file ảnh hợp lệ để OCR"
        logger.debug(f"[OCR] Bỏ qua banner (không có file): {src_url[:80]}")
        return result

    # ── OCR từng ảnh / frame ──
    frames_ocr_texts: list[str] = []
    for img_path in paths_to_ocr:
        text = run_ocr(img_path, ocr_reader)
        if text:
            frames_ocr_texts.append(text)

    result["frames_ocr"] = frames_ocr_texts

    # Merge tất cả text thành 1 chuỗi để cascade
    merged_raw  = " ".join(frames_ocr_texts).strip()
    merged_norm = normalize_text(merged_raw)

    result["ocr_raw"]  = merged_raw
    result["ocr_norm"] = merged_norm

    if not merged_raw:
        logger.debug(f"[OCR] Không đọc được text từ banner: {local_path}")
        return result

    banner_id = os.path.basename(local_path or src_url or "unknown")
    logger.info(f"[OCR] Analyzing '{banner_id}' | text: '{merged_raw[:80]}'")

    # ════════════════════
    # TẦNG 1 — Exact match
    # ════════════════════
    hit = tier1_exact(merged_norm, keywords)
    if hit:
        result.update({
            "matched":         True,
            "tier_hit":        1,
            "keyword":         hit["keyword"],
            "field":           hit["field"],
            "violation_level": hit["violation_level"],
            "score":           hit["score"],
            "score_type":      hit["score_type"],
        })
        logger.info(f"[OCR] ★ MATCH T1 | '{banner_id}' → '{hit['keyword']}'")
        return result  # Short-circuit: không cần T2/T3

    logger.debug(f"[OCR] T1 miss → thử T2 | '{banner_id}'")

    # ════════════════════
    # TẦNG 2 — Fuzzy match
    # ════════════════════
    hit = tier2_fuzzy(merged_norm, keywords)
    if hit:
        result.update({
            "matched":         True,
            "tier_hit":        2,
            "keyword":         hit["keyword"],
            "field":           hit["field"],
            "violation_level": hit["violation_level"],
            "score":           hit["score"],
            "score_type":      hit["score_type"],
        })
        logger.info(
            f"[OCR] ★ MATCH T2 | '{banner_id}' → '{hit['keyword']}' "
            f"score={hit['score']:.1f}"
        )
        return result  # Short-circuit: không cần T3

    logger.debug(f"[OCR] T2 miss → thử T3 | '{banner_id}'")

    # ════════════════════
    # TẦNG 3 — Semantic embedding
    # ════════════════════
    if embedding_model is None:
        # Model chưa được load (lazy) → không thể chạy T3
        logger.debug(f"[OCR] T3 skip (model None) | '{banner_id}'")
        return result

    hit = tier3_semantic(merged_raw, seed_phrases, embedding_model)
    if hit:
        result.update({
            "matched":         True,
            "tier_hit":        3,
            "keyword":         hit["keyword"],
            "field":           hit["field"],
            "violation_level": hit["violation_level"],
            "score":           hit["score"],
            "score_type":      hit["score_type"],
        })
        logger.info(
            f"[OCR] ★ MATCH T3 | '{banner_id}' → '{hit['keyword']}' "
            f"cosine={hit['score']:.3f}"
        )
    else:
        logger.info(f"[OCR] ✗ No match (T1/T2/T3) | '{banner_id}'")

    return result


# ══════════════════════════════════════════════════════════════
# SECTION 9 — PUBLIC API
# ══════════════════════════════════════════════════════════════

def run_ocr_pipeline(
    banners: list[dict],
    keywords_csv: str = "keywords/Keywords_v1.csv",
    seed_phrases: list[str] = GAMBLING_SEED_PHRASES,
    enable_tier3: bool = True,
) -> list[dict]:
    """
    Entry point của OCR pipeline. Nhận danh sách banner từ step2,
    trả về danh sách dict kết quả phân tích (1 phần tử / banner).

    Shared resource initialization (chạy 1 lần, tái dùng cho tất cả banner):
      - EasyOCR reader       : luôn khởi tạo nếu có banner hợp lệ
      - SentenceTransformer  : lazy-init — chỉ load khi CÓ banner nào
                               vượt qua T1+T2 mà không match (tiết kiệm RAM)

    Args:
        banners      : list[dict] từ evidence["banners"] (output của step2)
        keywords_csv : đường dẫn đến Keywords_v1.csv
        seed_phrases : danh sách câu mẫu cho Tầng 3
        enable_tier3 : False để tắt hoàn toàn Tầng 3 (dùng khi debug / test nhanh)

    Returns:
        list[dict] — kết quả phân tích từng banner
    """
    if not banners:
        logger.info("[OCR] Không có banner để phân tích.")
        return []

    logger.info(
        f"\n{'='*60}\n"
        f"[OCR] Bắt đầu OCR Pipeline — {len(banners)} banner(s)\n"
        f"{'='*60}"
    )

    # ── Load keywords ──
    keywords = load_keywords(keywords_csv)
    if not keywords:
        logger.warning("[OCR] Danh sách keyword rỗng — T1/T2 sẽ không match được gì.")

    # ── Init EasyOCR reader (1 lần) ──
    ocr_reader = _init_ocr_reader()

    # ── Embedding model: lazy, chưa load ──
    embedding_model = None
    tier3_loaded    = False

    results: list[dict] = []

    for i, banner in enumerate(banners, start=1):
        logger.info(
            f"[OCR] ── Banner {i}/{len(banners)}: "
            f"{banner.get('case', '?')} | "
            f"{os.path.basename(banner.get('local_path', '') or banner.get('src_url', ''))}"
        )

        # Chạy cascade với model hiện tại (có thể None nếu T3 chưa load)
        result = analyze_banner(
            banner,
            keywords,
            ocr_reader,
            seed_phrases,
            embedding_model=embedding_model,
        )

        # ── Lazy-load embedding model khi cần (T3) ──
        # Điều kiện: T3 được bật, banner này chưa match (T1+T2 đều miss),
        #            có text để embed, model chưa load.
        needs_tier3 = (
            enable_tier3
            and not result.get("matched")
            and result.get("ocr_raw", "").strip()
            and not tier3_loaded
        )

        if needs_tier3:
            logger.info("[OCR] → Lazy-loading Tầng 3 (Semantic Embedding)...")
            embedding_model = _init_embedding_model()
            tier3_loaded = True  # Đánh dấu đã thử load (dù thành công hay không)

            if embedding_model is not None:
                # Re-run chỉ tầng 3 cho banner hiện tại
                # (T1/T2 đã chạy và miss rồi — chỉ cần T3)
                hit = tier3_semantic(result["ocr_raw"], seed_phrases, embedding_model)
                if hit:
                    result.update({
                        "matched":         True,
                        "tier_hit":        3,
                        "keyword":         hit["keyword"],
                        "field":           hit["field"],
                        "violation_level": hit["violation_level"],
                        "score":           hit["score"],
                        "score_type":      hit["score_type"],
                    })
                    logger.info(
                        f"[OCR] ★ MATCH T3 (lazy) | "
                        f"'{hit['keyword']}' cosine={hit['score']:.3f}"
                    )

        elif enable_tier3 and not result.get("matched") and tier3_loaded and embedding_model:
            # Model đã load từ banner trước → dùng luôn cho banner này
            hit = tier3_semantic(result["ocr_raw"], seed_phrases, embedding_model)
            if hit:
                result.update({
                    "matched":         True,
                    "tier_hit":        3,
                    "keyword":         hit["keyword"],
                    "field":           hit["field"],
                    "violation_level": hit["violation_level"],
                    "score":           hit["score"],
                    "score_type":      hit["score_type"],
                })
                logger.info(
                    f"[OCR] ★ MATCH T3 | "
                    f"'{hit['keyword']}' cosine={hit['score']:.3f}"
                )

        results.append(result)

    # ── Summary log ──
    matched_count = sum(1 for r in results if r.get("matched"))
    tier_dist = {1: 0, 2: 0, 3: 0}
    for r in results:
        t = r.get("tier_hit")
        if t in tier_dist:
            tier_dist[t] += 1

    logger.info(
        f"\n[OCR] Pipeline complete.\n"
        f"  Tổng banner phân tích : {len(results)}\n"
        f"  Số banner có match    : {matched_count}\n"
        f"  Phân bổ tầng          : T1={tier_dist[1]} | T2={tier_dist[2]} | T3={tier_dist[3]}\n"
    )

    return results
