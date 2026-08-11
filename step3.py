"""
Step 3: AI/ML Evidence Engine — Branch 2: Content Model

Luồng xử lý:
  1. Text Segmenter  : cắt DOM text thành segments 256 tokens
  2. Overlap Handler : từ segment 2 trở đi, lùi 30 tokens để tìm
                       điểm ngắt câu (dấu phẩy/chấm) giúp segment có nghĩa
  3. Content Model   : PhoBERT fine-tuned chạy 2 task song song:
                         Task 1 → label (0=An toàn / 1=Độc hại)
                         Task 2 → loại website (Cờ bạc, 18+, v.v.)
  4. Max Pooling     : tổng hợp kết quả từ tất cả segments

Usage:
    from step3 import run_content_model
    result = run_content_model(dom_text)
"""

import re
import sys
import os
import torch

# Thêm thư mục model vào sys.path để import model_loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model"))
from model_loader import get_content_model, DEVICE

# ==============================================================================
# CONFIG
# ==============================================================================

MAX_TOKENS     = 256   # Số token tối đa mỗi segment
OVERLAP_TOKENS = 30    # Số token lùi về phía trước để tìm điểm ngắt câu

# Mapping loại website (Task 2)
TYPE_MAPPING = {
    -1: "Không hoạt động",
    0:  "Báo chí",
    1:  "18+",
    2:  "Cờ bạc",
    3:  "Vay",
    4:  "Tiền ảo",
    5:  "Tổ chức",
    6:  "E-commerce",
    7:  "MXH",
    8:  "Game",
    9:  "Chưa xác định",
    10: "Phim ảnh",
    11: "Thể thao",
}

# ==============================================================================
# TEXT SEGMENTER WITH OVERLAP
# ==============================================================================

def segment_text(text: str, tokenizer=None, max_words: int = 256, overlap_words: int = 40) -> list[str]:
    """
    Cắt `text` thành danh sách segments, mỗi segment tối đa `max_words` từ.
    Sử dụng từ điển pyvi (nếu có) hoặc split space và tìm điểm ngắt câu bằng `.!?。！？\n`.
    """
    if not text or not isinstance(text, str):
        return []
    
    clean_text = re.sub(r"\s+", " ", text.strip())
    try:
        from pyvi import ViTokenizer
        words, _ = ViTokenizer.spacy_tokenize(clean_text)
    except Exception:
        words = clean_text.split()

    if len(words) <= max_words:
        return [" ".join(words).replace("_", " ")]

    segments = []
    start = 0
    while start < len(words):
        end = start + max_words
        if end >= len(words):
            segment_words = words[start:]
            start = len(words)
        else:
            cutoff = end
            search_from = max(start, end - 100)
            for i in range(end - 1, search_from - 1, -1):
                word = words[i].replace("_", " ")
                if any(word.endswith(p) for p in ".!?。！？\n"):
                    cutoff = i + 1
                    break
            segment_words = words[start:cutoff]
            start = max(cutoff - overlap_words, 0)

        segment_text = " ".join(segment_words).replace("_", " ").strip()
        if len(segment_text) > 30:
            segments.append(segment_text)
    return segments



# ==============================================================================
# INFERENCE TRÊN 1 SEGMENT
# ==============================================================================

@torch.no_grad()
def _predict_segment(text: str, model, tokenizer) -> dict:
    """
    Chạy inference Content Model cho 1 segment.
    Trả về dict chứa kết quả Task 1 và Task 2.
    """
    enc = tokenizer(
        text,
        truncation=True,
        max_length=MAX_TOKENS,
        padding="max_length",
        return_tensors="pt",
    )
    input_ids      = enc["input_ids"].to(DEVICE)
    attention_mask = enc["attention_mask"].to(DEVICE)

    # Task 1: Phishing / Credibility
    out1   = model(input_ids=input_ids, attention_mask=attention_mask, task_id=1)
    probs1 = torch.softmax(out1.logits, dim=-1).cpu().numpy()[0]
    label1 = int(probs1.argmax())

    # Task 2: Website Category
    out2   = model(input_ids=input_ids, attention_mask=attention_mask, task_id=2)
    probs2 = torch.softmax(out2.logits, dim=-1).cpu().numpy()[0]
    label2 = int(probs2.argmax())

    return {
        "label":          label1,
        "label_name":     "Độc hại" if label1 == 1 else "An toàn",
        "prob_safe":      float(probs1[0]),
        "prob_malicious": float(probs1[1]),
        "type":           label2,
        "type_name":      TYPE_MAPPING.get(label2, "Chưa xác định"),
        "type_probs":     probs2.tolist(),
    }


# ==============================================================================
# MAX POOLING AGGREGATOR
# ==============================================================================

def _aggregate_results(segment_results: list[dict], total_segments_count: int) -> dict:
    """
    Tổng hợp kết quả từ tất cả segments:

    - Final label  : max(label_i) — chỉ cần 1 segment độc hại → cả trang độc hại
    - Final type   : bầu cử đa số (voting-based) trên các segments đã chạy
    - max_malicious_prob: xác suất độc hại cao nhất trong các segments
    - malicious_segment_count: số segments bị nhãn độc hại
    """
    from collections import Counter
    if not segment_results:
        return {
            "final_label":             0,
            "final_label_name":        "An toàn",
            "final_type":              9,
            "final_type_name":         "Chưa xác định",
            "max_malicious_prob":      0.0,
            "malicious_segment_count": 0,
            "total_segments":          total_segments_count,
        }

    # Max Pooling cho label (Task 1)
    final_label = max(r["label"] for r in segment_results)
    max_mal_prob = max(r["prob_malicious"] for r in segment_results)
    mal_count = sum(1 for r in segment_results if r["label"] == 1)

    # Voting cho type (Task 2)
    type_votes = [r["type"] for r in segment_results]
    counter = Counter(type_votes)
    ranked = counter.most_common()
    
    # Lọc bỏ class 9 (Chưa xác định) trừ khi không còn class nào khác
    without_9 = [x for x in ranked if x[0] != 9]
    if 9 in counter:
        without_9.append((9, counter[9]))
        
    final_type = without_9[0][0] if without_9 else 9

    return {
        "final_label":             final_label,
        "final_label_name":        "Độc hại" if final_label == 1 else "An toàn",
        "final_type":              final_type,
        "final_type_name":         TYPE_MAPPING.get(final_type, "Chưa xác định"),
        "max_malicious_prob":      round(max_mal_prob, 4),
        "malicious_segment_count": mal_count,
        "total_segments":          total_segments_count,
    }


# ==============================================================================
# PUBLIC API
# ==============================================================================

def run_content_model(dom_text: str, mode: str = "quick") -> dict:
    """
    Chạy toàn bộ Branch 2 — Content Model pipeline.

    Args:
        dom_text: Text thô được cào từ DOM của trang web.
        mode: "quick" (early stop khi phát hiện độc hại) hoặc "full" (quét hết).

    Returns:
        dict: {
            "final_label"            : int   (0=An toàn / 1=Độc hại),
            "final_label_name"       : str,
            "final_type"             : int   (0-11),
            "final_type_name"        : str,
            "max_malicious_prob"     : float,
            "malicious_segment_count": int,
            "total_segments"         : int,
            "segment_results"        : list[dict],  # chi tiết từng segment
            "model"                  : str,
        }
    """
    if not dom_text or not dom_text.strip():
        return {
            "final_label":             0,
            "final_label_name":        "An toàn",
            "final_type":              9,
            "final_type_name":         "Chưa xác định",
            "max_malicious_prob":      0.0,
            "malicious_segment_count": 0,
            "total_segments":          0,
            "segment_results":         [],
            "model":                   "v2_multitask",
            "note":                    "DOM text rỗng, bỏ qua phân tích.",
        }

    model, tokenizer = get_content_model()

    # 1. Segmentation với overlap handler (dùng word-based segmenter)
    segments = segment_text(dom_text, tokenizer, MAX_TOKENS, OVERLAP_TOKENS)

    if not segments:
        return {
            "final_label":             0,
            "final_label_name":        "An toàn",
            "final_type":              9,
            "final_type_name":         "Chưa xác định",
            "max_malicious_prob":      0.0,
            "malicious_segment_count": 0,
            "total_segments":          0,
            "segment_results":         [],
            "model":                   "v2_multitask",
            "note":                    "Không tạo được segment từ text.",
        }

    # 2. Inference từng segment
    segment_results = []
    for i, seg in enumerate(segments):
        result = _predict_segment(seg, model, tokenizer)
        result["segment_index"] = i
        result["segment_preview"] = seg[:100] + "..." if len(seg) > 100 else seg
        segment_results.append(result)
        
        # Early Stop nếu tìm thấy segment độc hại
        if result["label"] == 1 and mode == "quick":
            print(f" [Early Stop] Phát hiện nội dung độc hại tại segment {i+1}! Dừng quét các segment tiếp theo.")
            break

    # 3. Aggregation (bầu cử đa số)
    aggregated = _aggregate_results(segment_results, len(segments))

    return {
        **aggregated,
        "segment_results": segment_results,
        "model":           "v2_multitask",
    }

