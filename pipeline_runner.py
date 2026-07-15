"""
pipeline_runner.py
──────────────────
Cầu nối giữa demo_app.py UI và pipeline thực (main.py logic).

Hai chế độ hoạt động:
  1. CACHE MODE  : Tìm kết quả đã có trong logs/ → load ngay (< 1 giây)
  2. LIVE MODE   : Chạy pipeline thực trong thread → callback cập nhật UI step-by-step

Sử dụng trong Streamlit qua st.session_state để tránh re-run vô hạn.
"""

import os
import re
import glob
import json
import threading
import time
from datetime import datetime
from typing import Callable, Optional


# ──────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────

LOGS_BASE = os.path.join("logs", "v1.0.4.1")
CSV_PATH  = "danh_sach_domain_whitelist.csv"

PIPELINE_STEPS = [
    {
        "id":    "step0",
        "label": "Step 0 — Whitelist & Domain Model",
        "icon":  "🗂️",
        "desc":  "Kiểm tra whitelist VNNIC + PhoBERT Domain Model phân loại sơ bộ",
        "weight": 10,   # % contribution to total progress
    },
    {
        "id":    "step1",
        "label": "Step 1 — Network Intelligence",
        "icon":  "🌐",
        "desc":  "Thu thập DNS, WHOIS, ASN, TLD risk, redirect chain",
        "weight": 15,
    },
    {
        "id":    "step2",
        "label": "Step 2 — Browser Evidence Collection",
        "icon":  "🖥️",
        "desc":  "Playwright stealth browser: thu thập banner, DOM text, stream URL",
        "weight": 35,
    },
    {
        "id":    "step3a",
        "label": "Step 3A — OCR Banner Engine",
        "icon":  "🔎",
        "desc":  "EasyOCR + 3-tier keyword matching (exact → fuzzy → semantic)",
        "weight": 20,
    },
    {
        "id":    "step3b",
        "label": "Step 3B — Content Model (PhoBERT)",
        "icon":  "🧠",
        "desc":  "PhoBERT fine-tuned phân loại DOM text theo 256-token segments",
        "weight": 10,
    },
    {
        "id":    "step4",
        "label": "Step 4 — Gemini AI Synthesis",
        "icon":  "✨",
        "desc":  "Gemini tổng hợp evidence → verdict + key signals + báo cáo",
        "weight": 10,
    },
]


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def normalize_domain(url: str) -> str:
    """Lấy domain sạch từ URL."""
    from urllib.parse import urlparse
    url = url.strip().lower()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        domain = domain.replace("www.", "").split(":")[0].strip(".")
        return domain
    except Exception:
        return ""


def safe_domain_name(domain: str) -> str:
    """Chuyển domain thành tên file-safe."""
    return re.sub(r'[\\/*?:"<>|]', "_", domain)


# ──────────────────────────────────────────────────────────────
# CACHE LOADER
# ──────────────────────────────────────────────────────────────

def find_cached_result(domain: str) -> Optional[dict]:
    """
    Tìm kết quả đã lưu trong logs/ cho domain này.
    Trả về dict với đầy đủ paths hoặc None nếu chưa có.
    """
    safe = safe_domain_name(domain)
    domain_dir = os.path.join(LOGS_BASE, domain)
    safe_dir   = os.path.join(LOGS_BASE, safe)

    found_dir = None
    for d in [domain_dir, safe_dir]:
        if os.path.isdir(d):
            found_dir = d
            break

    # Fallback: tìm partial match
    if not found_dir:
        try:
            for entry in os.listdir(LOGS_BASE):
                if domain in entry or entry in domain:
                    candidate = os.path.join(LOGS_BASE, entry)
                    if os.path.isdir(candidate):
                        found_dir = candidate
                        break
        except Exception:
            pass

    if not found_dir:
        return None

    # Tìm _report_ và _final_ JSON
    report_files = glob.glob(os.path.join(found_dir, "*_report_*.json"))
    final_files  = glob.glob(os.path.join(found_dir, "*_final_*.json"))
    step2_files  = glob.glob(os.path.join(found_dir, "*_step2_*.json"))
    step1_files  = glob.glob(os.path.join(found_dir, "*_step1_*.json"))

    if not report_files:
        return None

    # Chọn file mới nhất
    report_path = sorted(report_files)[-1]
    final_path  = sorted(final_files)[-1]  if final_files  else None
    step2_path  = sorted(step2_files)[-1]  if step2_files  else None
    step1_path  = sorted(step1_files)[-1]  if step1_files  else None

    # Load JSON
    def _load(p):
        if not p or not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    report_data = _load(report_path)
    final_data  = _load(final_path)
    step2_data  = _load(step2_path)
    step1_data  = _load(step1_path)

    if not report_data:
        return None

    return {
        "domain":      domain,
        "found_dir":   found_dir,
        "report_path": report_path,
        "final_path":  final_path,
        "step2_path":  step2_path,
        "step1_path":  step1_path,
        "report_data": report_data,
        "final_data":  final_data,
        "step2_data":  step2_data,
        "step1_data":  step1_data,
        "source":      "cache",
        "scanned_at":  report_data.get("analyzed_at", "N/A"),
    }


def list_all_cached_domains() -> list[dict]:
    """
    Liệt kê tất cả domains đã có kết quả trong logs/.
    Trả về list[dict] để hiển thị trong History tab.
    """
    results = []
    if not os.path.isdir(LOGS_BASE):
        return results

    for entry in sorted(os.listdir(LOGS_BASE)):
        entry_path = os.path.join(LOGS_BASE, entry)
        if not os.path.isdir(entry_path):
            continue

        report_files = glob.glob(os.path.join(entry_path, "*_report_*.json"))
        if not report_files:
            continue

        report_path = sorted(report_files)[-1]
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                rdata = json.load(f)

            verdict    = rdata.get("verdict", "N/A")
            confidence = rdata.get("confidence", 0)
            analyzed   = rdata.get("analyzed_at", "N/A")
            violations = rdata.get("violation_types", [])
            rec_action = rdata.get("recommended_action", "N/A")
            inp_sum    = rdata.get("input_summary", {})

            results.append({
                "domain":      rdata.get("domain", entry),
                "verdict":     verdict,
                "confidence":  confidence,
                "analyzed_at": analyzed,
                "violations":  violations,
                "action":      rec_action,
                "ocr_banners": inp_sum.get("ocr_banner_count", 0),
                "ocr_flagged": inp_sum.get("ocr_flagged_count", 0),
                "risk_score":  inp_sum.get("risk_score", "N/A"),
                "report_path": report_path,
                "domain_dir":  entry_path,
            })
        except Exception:
            continue

    return results


# ──────────────────────────────────────────────────────────────
# LIVE PIPELINE RUNNER (threaded)
# ──────────────────────────────────────────────────────────────

class PipelineState:
    """Shared state object cho live pipeline run."""
    def __init__(self):
        self.status      = "idle"       # idle | running | done | error
        self.progress    = 0            # 0–100
        self.current_step_id   = None
        self.completed_steps   = []
        self.logs        = []           # list of log lines (str)
        self.result      = None         # final cached result dict khi xong
        self.error       = None

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")

    def advance(self, step_id: str, weight: int):
        self.current_step_id = step_id
        # Tính progress tích lũy
        completed_weight = sum(
            s["weight"] for s in PIPELINE_STEPS
            if s["id"] in self.completed_steps
        )
        self.progress = min(99, completed_weight)

    def complete_step(self, step_id: str):
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)
        completed_weight = sum(
            s["weight"] for s in PIPELINE_STEPS
            if s["id"] in self.completed_steps
        )
        self.progress = min(99, completed_weight)


def run_pipeline_live(url: str, state: PipelineState):
    """
    Chạy pipeline thực trong background thread.
    Cập nhật `state` liên tục để UI có thể poll.

    Nếu import lỗi (thiếu deps) → fallback về cache mode.
    """
    state.status = "running"
    state.log(f"Bắt đầu phân tích: {url}")

    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        _sys.stderr.reconfigure(encoding='utf-8', errors='replace')

        from step0 import normalize_domain as nd, check_domain_in_database, run_domain_model_check
        from evidence import build_evidence_buffer
        from step2 import run_step2
        from step3 import run_content_model
        from ocr_banner import run_ocr_pipeline
        from step4 import run_step4
        import re as _re
        from datetime import datetime as dt

        # ── URL normalize ──
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        domain = nd(url)
        state.log(f"Domain đã chuẩn hóa: {domain}")

        safe = _re.sub(r'[\\/*?:"<>|]', "_", domain)
        logs_dir = os.path.join(LOGS_BASE, safe)
        os.makedirs(logs_dir, exist_ok=True)
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")

        # ── Step 0 ──
        state.advance("step0", 10)
        state.log("Step 0: Kiểm tra whitelist VNNIC...")
        step0_result = check_domain_in_database(url, CSV_PATH)
        state.log(f"  Whitelist: {'Có' if step0_result.get('in_database') else 'Không'}")

        state.log("Step 0: Chạy Domain Model (PhoBERT)...")
        evidence_buffer = build_evidence_buffer(domain, url)
        evidence_buffer["step0"] = step0_result

        try:
            dm_result = run_domain_model_check(domain, evidence_buffer)
            evidence_buffer["step0"]["domain_model"] = dm_result
            state.log(f"  Domain Model: {dm_result.get('label_name')} ({dm_result.get('prob_malicious', 0)*100:.1f}% độc hại)")
        except Exception as e:
            state.log(f"  [WARN] Domain Model lỗi: {e}")

        state.complete_step("step0")
        state.log("✅ Step 0 hoàn thành")

        # ── Step 1 ──
        state.advance("step1", 15)
        state.log("Step 1: Thu thập thông tin mạng (DNS, WHOIS, ASN)...")

        # Handle redirect cross-domain
        _redirect_info = evidence_buffer.get("redirect_info", {})
        if _redirect_info.get("domain_hopping"):
            _domains_seen = _redirect_info.get("domains_seen", [])
            _final_domain = _domains_seen[-1] if _domains_seen else None
            if _final_domain and _final_domain != domain:
                state.log(f"  🔀 Redirect phát hiện: {domain} → {_final_domain}")
                domain = _final_domain
                safe = _re.sub(r'[\\/*?:"<>|]', "_", domain)
                logs_dir = os.path.join(LOGS_BASE, safe)
                os.makedirs(logs_dir, exist_ok=True)

        step1_path = os.path.join(logs_dir, f"{safe}_step1_{timestamp}.json")
        with open(step1_path, "w", encoding="utf-8") as f:
            json.dump(evidence_buffer, f, indent=4, ensure_ascii=False, default=str)
        state.log(f"  Đã lưu Step 1: {os.path.basename(step1_path)}")
        state.complete_step("step1")
        state.log("✅ Step 1 hoàn thành")

        # ── Step 2 ──
        state.advance("step2", 35)
        state.log("Step 2: Playwright browser — thu thập banner & DOM text...")
        state.log("  (Quá trình này mất 30–90 giây, vui lòng chờ...)")

        browser_url = url
        step2_evidence = run_step2(domain, browser_url)
        evidence_buffer["step2_evidence"] = step2_evidence

        if step2_evidence.get("redirect_cross_domain"):
            redirected_domain = step2_evidence.get("target_domain", domain)
            if redirected_domain and redirected_domain != domain:
                domain = redirected_domain
                safe = _re.sub(r'[\\/*?:"<>|]', "_", domain)
                logs_dir = os.path.join(LOGS_BASE, safe)
                os.makedirs(logs_dir, exist_ok=True)

        banners = step2_evidence.get("banners", [])
        state.log(f"  Thu thập được: {len(banners)} banner")
        streams = step2_evidence.get("streams", [])
        state.log(f"  Stream URLs phát hiện: {len(streams)}")

        step2_path = os.path.join(logs_dir, f"{safe}_step2_{timestamp}.json")
        with open(step2_path, "w", encoding="utf-8") as f:
            json.dump(step2_evidence, f, indent=4, ensure_ascii=False, default=str)
        state.complete_step("step2")
        state.log("✅ Step 2 hoàn thành")

        # ── Step 3 ──
        evidence_buffer["step3_evidence"] = {"branch1_ocr": None, "branch2_content_model": None}

        # Branch 1: OCR
        state.advance("step3a", 20)
        ad_banners = [b for b in banners if b.get("local_path")]
        state.log(f"Step 3A: OCR Engine — phân tích {len(ad_banners)} banner betting...")

        if ad_banners:
            try:
                ocr_results = run_ocr_pipeline(ad_banners, keywords_csv="keywords/Keywords_v1.csv")
                flagged = [r for r in ocr_results if r.get("matched")]
                evidence_buffer["step3_evidence"]["branch1_ocr"] = {
                    "banner_count":       len(ocr_results),
                    "flagged_count":      len(flagged),
                    "has_gambling_banner": len(flagged) > 0,
                    "results":            ocr_results,
                }
                state.log(f"  Phát hiện {len(flagged)}/{len(ocr_results)} banner vi phạm")
            except Exception as e:
                state.log(f"  [WARN] OCR lỗi: {e}")
                evidence_buffer["step3_evidence"]["branch1_ocr"] = {"error": str(e)}
        else:
            evidence_buffer["step3_evidence"]["branch1_ocr"] = {
                "banner_count": 0, "flagged_count": 0,
                "has_gambling_banner": False, "results": [],
            }
            state.log("  Không có banner betting hợp lệ để OCR")

        state.complete_step("step3a")
        state.log("✅ Step 3A hoàn thành")

        # Branch 2: Content Model
        state.advance("step3b", 10)
        dom_text = step2_evidence.get("dom_text", "")
        state.log(f"Step 3B: Content Model — phân tích DOM text ({len(dom_text)} ký tự)...")

        if dom_text:
            try:
                content_result = run_content_model(dom_text)
                evidence_buffer["step3_evidence"]["branch2_content_model"] = content_result
                state.log(f"  Kết quả: {content_result.get('final_type_name', 'N/A')} "
                          f"({'ĐỘC HẠI' if content_result.get('final_label') == 1 else 'AN TOÀN'})")
            except Exception as e:
                state.log(f"  [WARN] Content Model lỗi: {e}")
                evidence_buffer["step3_evidence"]["branch2_content_model"] = {"error": str(e)}
        else:
            state.log("  Không có DOM text")
            evidence_buffer["step3_evidence"]["branch2_content_model"] = {
                "note": "Không có DOM text.", "final_label": None
            }

        state.complete_step("step3b")
        state.log("✅ Step 3B hoàn thành")

        # Save final combined
        final_file = f"{safe}_final_{timestamp}.json"
        final_path = os.path.join(logs_dir, final_file)
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(evidence_buffer, f, indent=4, ensure_ascii=False, default=str)
        state.log(f"  Đã lưu Final JSON: {final_file}")

        # ── Step 4: Gemini ──
        state.advance("step4", 10)
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            state.log("Step 4: Gửi evidence đến Gemini API...")
            try:
                run_step4(evidence_buffer, api_key=gemini_key, domain=domain,
                          timestamp=timestamp, logs_dir=logs_dir)
                state.log("  Gemini tổng hợp hoàn thành")
            except Exception as e:
                state.log(f"  [WARN] Gemini API lỗi: {e}")
        else:
            state.log("  [INFO] Không có GEMINI_API_KEY — bỏ qua Step 4")

        state.complete_step("step4")
        state.log("✅ Step 4 hoàn thành")

        # Load result từ cache
        state.result = find_cached_result(domain) or find_cached_result(safe)
        state.progress = 100
        state.status   = "done"
        state.log("🎉 Phân tích hoàn tất!")

    except ImportError as e:
        state.log(f"[ERROR] Thiếu dependency: {e}")
        state.log("Thử load từ cache...")
        domain = normalize_domain(url)
        cached = find_cached_result(domain)
        if cached:
            state.result   = cached
            state.progress = 100
            state.status   = "done"
            state.log(f"✅ Đã load kết quả từ cache cho {domain}")
        else:
            state.status = "error"
            state.error  = f"Thiếu dependency và không tìm thấy cache: {e}"

    except Exception as e:
        state.status = "error"
        state.error  = str(e)
        state.log(f"[ERROR] Pipeline lỗi: {e}")


def start_pipeline_thread(url: str, state: PipelineState) -> threading.Thread:
    """Khởi chạy pipeline trong background thread."""
    t = threading.Thread(target=run_pipeline_live, args=(url, state), daemon=True)
    t.start()
    return t
