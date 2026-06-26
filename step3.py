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
}

# ==============================================================================
# TEXT SEGMENTER WITH OVERLAP
# ==============================================================================

def _find_sentence_break(tokens: list, start: int, window: int) -> int:
    """
    Tìm vị trí ngắt câu trong vùng [start - window, start).
    Ưu tiên dấu chấm (.) trước, sau đó dấu phẩy (,).
    Trả về index token tốt nhất để bắt đầu segment mới,
    hoặc `start` nếu không tìm thấy điểm ngắt.
    """
    # Các token tương ứng dấu chấm / phẩy trong vocab PhoBERT
    BREAK_TOKENS_PRIORITY = [
        [".", "▁."],   # dấu chấm (ưu tiên cao)
        [",", "▁,"],   # dấu phẩy
    ]

    search_start = max(0, start - window)
    for break_set in BREAK_TOKENS_PRIORITY:
        # Duyệt ngược để tìm điểm ngắt gần nhất trước `start`
        for i in range(start - 1, search_start - 1, -1):
            if tokens[i] in break_set:
                # Trả về token NGAY SAU dấu câu
                return i + 1
    return start


def segment_text(text: str, tokenizer, max_tokens: int = MAX_TOKENS, overlap_tokens: int = OVERLAP_TOKENS) -> list[str]:
    """
    Cắt `text` thành danh sách segments, mỗi segment tối đa `max_tokens` tokens.

    Từ segment thứ 2 trở đi:
    - Lùi `overlap_tokens` về phía trước từ vị trí bắt đầu tự nhiên
    - Tìm vị trí ngắt câu (dấu chấm ưu tiên, sau đó dấu phẩy)
    - Bắt đầu segment mới từ điểm ngắt đó

    Điều này đảm bảo mỗi segment bắt đầu từ đầu câu, tránh cắt câu dở dang.
    """
    if not text or not text.strip():
        return []

    # Tokenize toàn bộ text (không giới hạn độ dài)
    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=False,
    )
    token_ids = encoded["input_ids"]
    token_strings = tokenizer.convert_ids_to_tokens(token_ids)

    if not token_ids:
        return []

    segments = []
    pos = 0  # Con trỏ vị trí hiện tại trong token_ids
    is_first_segment = True

    while pos < len(token_ids):
        end = min(pos + max_tokens, len(token_ids))

        if is_first_segment:
            # Segment đầu: lấy thẳng từ đầu
            seg_ids = token_ids[pos:end]
            is_first_segment = False
        else:
            # Segment tiếp theo: tìm điểm ngắt câu trong vùng overlap
            actual_start = _find_sentence_break(token_strings, pos, overlap_tokens)
            seg_ids = token_ids[actual_start:min(actual_start + max_tokens, len(token_ids))]
            end = actual_start + len(seg_ids)

        # Decode tokens về text
        seg_text = tokenizer.decode(seg_ids, skip_special_tokens=True)
        seg_text = seg_text.strip()

        if seg_text:
            segments.append(seg_text)

        pos = end

        # Guard: tránh vòng lặp vô hạn
        if pos <= 0:
            break

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

def _aggregate_results(segment_results: list[dict]) -> dict:
    """
    Tổng hợp kết quả từ tất cả segments bằng Max Pooling:

    - Final label  : max(label_i) — chỉ cần 1 segment độc hại → cả trang độc hại
    - Final type   : loại có xác suất trung bình cao nhất trên tất cả segments
    - max_malicious_prob: xác suất độc hại cao nhất trong các segments (để debug)
    - malicious_segment_count: số segments bị nhãn độc hại
    """
    if not segment_results:
        return {
            "final_label":             0,
            "final_label_name":        "An toàn",
            "final_type":              9,
            "final_type_name":         "Chưa xác định",
            "max_malicious_prob":      0.0,
            "malicious_segment_count": 0,
            "total_segments":          0,
        }

    # Max Pooling cho label (Task 1)
    final_label = max(r["label"] for r in segment_results)
    max_mal_prob = max(r["prob_malicious"] for r in segment_results)
    mal_count = sum(1 for r in segment_results if r["label"] == 1)

    # Average Pooling cho type (Task 2) — lấy loại có avg prob cao nhất
    n_types = len(segment_results[0]["type_probs"])
    avg_type_probs = [0.0] * n_types
    for r in segment_results:
        for i, p in enumerate(r["type_probs"]):
            avg_type_probs[i] += p
    avg_type_probs = [p / len(segment_results) for p in avg_type_probs]
    final_type = int(avg_type_probs.index(max(avg_type_probs)))

    return {
        "final_label":             final_label,
        "final_label_name":        "Độc hại" if final_label == 1 else "An toàn",
        "final_type":              final_type,
        "final_type_name":         TYPE_MAPPING.get(final_type, "Chưa xác định"),
        "max_malicious_prob":      round(max_mal_prob, 4),
        "malicious_segment_count": mal_count,
        "total_segments":          len(segment_results),
    }


# ==============================================================================
# PUBLIC API
# ==============================================================================

def run_content_model(dom_text: str) -> dict:
    """
    Chạy toàn bộ Branch 2 — Content Model pipeline.

    Args:
        dom_text: Text thô được cào từ DOM của trang web.

    Returns:
        dict: {
            "final_label"            : int   (0=An toàn / 1=Độc hại),
            "final_label_name"       : str,
            "final_type"             : int   (0-8),
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

    # 1. Segmentation với overlap handler
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

    # 3. Max Pooling aggregation
    aggregated = _aggregate_results(segment_results)

    return {
        **aggregated,
        "segment_results": segment_results,
        "model":           "v2_multitask",
    }
