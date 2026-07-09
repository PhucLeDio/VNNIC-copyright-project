"""
Step 4: Decision & Reporting Engine — Gemini API Synthesis

Luồng xử lý:
  1. Reducer   : trích xuất ~25 trường thiết yếu từ final_json → slim_payload
                 (giảm 60-90% token so với gửi nguyên file)
  2. Gemini API: nhận slim_payload + prompt tối ưu → verdict JSON
  3. Enricher  : ghép thêm thông tin phụ (IP, redirect, registrar...) vào report
  4. Save      : lưu report vào report/<domain>/

Usage (standalone):
    python step4.py logs/<domain>/<domain>_final_<timestamp>.json

Usage (từ main.py):
    from step4 import run_step4
    report = run_step4(evidence_buffer, api_key=os.getenv("GEMINI_API_KEY"))
"""

import json
import os
import re
import sys
from datetime import datetime
from dotenv import load_dotenv

# Fix Unicode output trên Windows terminal
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ==============================================================================
# CONFIG
# ==============================================================================

GEMINI_MODEL   = "gemini-3.5-flash"
REPORT_DIR     = "report"

# Các trường OCR giữ lại (chỉ banner đã matched)
OCR_KEEP_FIELDS = {"keyword", "tier_hit", "field"}

load_dotenv()  # loads .env from current directory

# ==============================================================================
# 1. REDUCER — Tạo slim payload
# ==============================================================================

def build_slim_payload(final_json: dict) -> dict:
    """
    Trích xuất chỉ các trường cần thiết từ final_json để giảm token.

    Bỏ hoàn toàn: banners (binary/URL dài), dom_text, segment_results,
    dns_records chi tiết, http_headers, 12 features số, redirect_history.

    Returns:
        dict slim với ~25 trường, sẵn sàng cho Gemini prompt.
    """
    slim = {}

    # ── Step 0: Whitelist + Domain Model ─────────────────────────────────────
    step0 = final_json.get("step0", {})
    slim["whitelist_hit"]        = step0.get("in_database", False)

    domain_model = step0.get("domain_model", {})
    slim["domain_model_label"]   = domain_model.get("label_name", "Không rõ")
    slim["domain_model_prob_mal"]= domain_model.get("prob_malicious", None)
    slim["domain_model_flag"]    = domain_model.get("flag", "OK")

    # ── Step 1: Network Evidence ──────────────────────────────────────────────
    slim["domain_age_days"]      = final_json.get("domain_age_days")
    slim["registrar"]            = final_json.get("registrar")
    slim["whois_privacy"]        = final_json.get("is_whois_privacy_active")

    tld_info = final_json.get("tld_info", {})
    slim["tld"]                  = tld_info.get("tld")
    slim["tld_risk"]             = tld_info.get("risk")

    slim["suspicious_hosting"]   = final_json.get("suspicious_hosting", False)
    slim["cloudflare"]           = final_json.get("cloudflare_detected", False)
    slim["mail_provider"]        = final_json.get("mail_provider")
    slim["risk_score"]           = final_json.get("risk_score")
    slim["legitimacy_score"]     = final_json.get("legitimacy_score")

    redirect_info = final_json.get("redirect_info", {})
    slim["redirect_cross_domain"]= redirect_info.get("cross_domain_count", 0)
    slim["redirect_final_url"]   = redirect_info.get("final_url")

    # ── Step 2: Browser Evidence ──────────────────────────────────────────────
    step2 = final_json.get("step2_evidence", {})
    slim["streams_found"]        = step2.get("streams_found", False)
    slim["stream_count"]         = step2.get("stream_count", 0)
    slim["keyword_hits"]         = step2.get("keyword_hits", [])

    # Chỉ giữ top-5 external domains (bỏ CDN thông thường)
    ext_domains = step2.get("external_resource_domains", [])
    slim["external_domains_top5"]= ext_domains[:5] if ext_domains else []

    # Footer pháp lý (Lớp 1 — L1)
    footer = step2.get("footer_analysis", {})
    slim["footer_legal"] = {
        "has_legal_footer":        footer.get("has_legal_footer"),
        "tax_code_found":          footer.get("tax_code_found"),
        "authority_found":         footer.get("authority_found"),
        "legal_notice_found":      footer.get("legal_notice_found"),
        "footer_anonymous":        footer.get("FOOTER_ANONYMOUS"),
        "has_telegram_contact":    footer.get("has_telegram_contact"),
        "has_ad_contact_only":     footer.get("has_ad_contact_only"),
        # Tiêu đề trang — phát hiện giả mạo thương hiệu
        "page_title":              (footer.get("meta_info") or {}).get("title"),
    }

    # Technical flags (Lớp 4 — L4)
    tech_flags = step2.get("technical_flags", {})
    slim["tech_flags"] = {
        "is_drm_protected":     tech_flags.get("is_drm_protected"),
        "stream_intercepted":   tech_flags.get("stream_intercepted"),
        "iframe_detected":      tech_flags.get("iframe_detected"),
        "popup_detected":       tech_flags.get("popup_detected"),
    }
    # Legitimate signals tổng hợp (Step 1)
    leg = final_json.get("legitimate_signals", {})
    slim["legitimate_signals"] = {
        "official_tld":        leg.get("official_tld"),
        "business_mail":       leg.get("business_mail"),
        "google_verification": leg.get("google_verification"),
        "spf_configured":      leg.get("spf_configured"),
        "total_signals":       leg.get("total_signals"),
    }

    # MX Analysis — site không có email doanh nghiệp → dấu hiệu streaming lậu
    mx = final_json.get("mx_analysis", {})
    slim["mx_streaming_only"]    = mx.get("possible_streaming_only_site", False)
    slim["has_business_mail"]    = mx.get("has_mx", False)

    # ── Step 3 Branch 1: OCR Banner Engine ───────────────────────────────────
    branch1 = (final_json.get("step3_evidence") or {}).get("branch1_ocr", {})
    slim["ocr_banner_count"]     = branch1.get("banner_count", 0)
    slim["ocr_flagged_count"]    = branch1.get("flagged_count", 0)
    slim["ocr_has_gambling"]     = branch1.get("has_gambling_banner", False)

    # Chỉ giữ các banner đã matched, chỉ lấy keyword + tier + field
    flagged_results = [
        r for r in (branch1.get("results") or [])
        if r.get("matched")
    ]
    slim["ocr_flagged_keywords"] = [
        {k: v for k, v in r.items() if k in OCR_KEEP_FIELDS}
        for r in flagged_results
    ]

    # ── Step 3 Branch 2: Content Model ───────────────────────────────────────
    branch2 = (final_json.get("step3_evidence") or {}).get("branch2_content_model", {})
    slim["content_label"]        = branch2.get("final_label")
    slim["content_label_name"]   = branch2.get("final_label_name")
    slim["content_type"]         = branch2.get("final_type_name")
    slim["content_prob_mal"]     = branch2.get("max_malicious_prob")
    slim["content_seg_malicious"]= branch2.get("malicious_segment_count", 0)
    slim["content_seg_total"]    = branch2.get("total_segments", 0)

    return slim


# ==============================================================================
# 2. PROMPT BUILDER — Tối ưu token
# ==============================================================================

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích vi phạm sở hữu trí tuệ (SHTT) trên internet tại Việt Nam, làm việc cho VNNIC.

Nhiệm vụ: Phân tích signals kỹ thuật từ hệ thống tự động và đưa ra kết luận vi phạm bản quyền/SHTT.

════════════════════════════════════════
KHUNG ĐỐI CHIẾU DẤU HIỆU VI PHẠM SHTT
(Nguồn: Hệ thống tiêu chí VNNIC)
========================================

LỚP 1 — Định danh & Pháp lý:
  [VP] Ẩn danh WHOIS (WHOIS Privacy bật); thông tin Footer chỉ có Telegram/Skype/Gmail rác; không có MST, giấy phép ICP/MXH.
  [OK] Thông tin chủ sở hữu công khai, trùng khớp doanh nghiệp Việt Nam; Footer đầy đủ Giấy phép, MST, địa chỉ.

LỚP 2 — Hạ tầng kỹ thuật:
  [VP] TLD lạ/rủi ro cao (.to, .cc, .xyz, .top, .club); thay đổi domain liên tục (thêm số/ký tự); dùng Cloudflare miễn phí/ẩn danh để che IP thực; redirect nhiều lần sang domain khác; domain mới < 90 ngày.
  [OK] TLD quốc gia .vn/.com.vn hoặc .com ổn định; hosting doanh nghiệp rõ ràng (Akamai, AWS, VNPT, Viettel).

LỚP 3 — Mô hình doanh thu:
  [VP] 100% banner nhà cái cá độ, game bài đổi thưởng (W88, Fun88, Kubet, Debet, 8xbet...); thanh toán qua thẻ cào/ví rác/crypto; pop-under tự động dẫn về trang đánh bạc.
  [OK] Quảng cáo programmatic sạch (Google Ads, brand chính thống); cổng thanh toán được NHNN cấp phép (Napas, VNPAY, MoMo).

LỚP 4 — Tính chất nội dung (theo lĩnh vực):
  Phim ảnh [VP]: Bản CAM quay lén; Vietsub tự dịch; phim đang chiếu rạp; không có DRM; link .m3u8/.mp4 bắt được dễ dàng.
  Bóng đá [VP]: Thu trộm tín hiệu K+/TV360/FPT Play; đè logo trang lậu (Xoilac, Thapcam); bình luận viên mạng dùng tục.
  Game [VP]: Bản Crack/Mod/APK cài ngoài; Private Server; hướng dẫn tắt antivirus.
  Cờ bạc [VP]: Trực tiếp: banner đá gà, cá cược, đặt cược, slot machine, bắn cá.

========================================
QUY TẮC PHÁN QUYẾT
========================================
- VI_PHAM: Có bằng chứng rõ ràng ở LỚP 3 hoặc LỚP 4 (nội dung vi phạm trực tiếp)
- NGHI_NGO: Chỉ có dấu hiệu LỚP 1 + LỚP 2 (hạ tầng/định danh đáng ngờ) nhưng chưa có nội dung vi phạm trực tiếp
- AN_TOAN: Không có dấu hiệu vi phạm ở cả 4 lớp

Trả về CHÍNH XÁC JSON schema sau, không có text thừa:
{
  "verdict": "VI_PHAM|NGHI_NGO|AN_TOAN",
  "confidence": <float 0.0-1.0>,
  "violation_types": [<ví dụ: "Cờ bạc", "Stream lậu", "Phim lậu", "Game crack", "Phishing">],
  "matched_criteria": {
    "lop1_phaplý": <true|false>,
    "lop2_hatang": <true|false>,
    "lop3_doanhthu": <true|false>,
    "lop4_noidung": <true|false>
  },
  "key_signals": [
    {"signal": "<mô tả ngắn>", "weight": "HIGH|MEDIUM|LOW", "layer": "L1|L2|L3|L4"}
  ],
  "summary_vi": "<tóm tắt 1-2 câu ngắn bằng tiếng Việt>",
  "recommended_action": "BLOCK|INVESTIGATE|MONITOR|WHITELIST",
  "analysis_note": "<ghi chú bất thường nếu có, hoặc null>"
}"""


def build_prompt(slim: dict) -> str:
    """
    Tạo user prompt từ slim payload.
    Dùng JSON nén (no indent) để tiết kiệm token.
    """
    payload_str = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
    return f"Phân tích signals kỹ thuật sau và đưa ra kết luận:\n{payload_str}"


# ==============================================================================
# 3. GEMINI API CALLER
# ==============================================================================

def _clean_json_text(raw: str) -> str:
    """
    Làm sạch raw text từ Gemini trước khi json.loads().
    CHỈ gọi khi parse trực tiếp đã thất bại.
    - Bỏ markdown code block (```json ... ```)
    - Bỏ trailing comma trước } hoặc ]
    - Bỏ “orphan text” bị lặp lại sau string value (hallucination của LLM)
    KHÔNG xóa // vì có thể nằm trong string value (URL, text...)
    """
    # 1. Bỏ markdown fence nếu có
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    # 2. Bỏ trailing comma trước } hoặc ] (JSON không cho phép)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    # 3. Xóa “orphan text”: văn bản rác bị lặp sau khi đóng string value
    #    Pattern điển hình (hallucination): "...rõ ràng."\nràng."\n}
    #    Regex: sau dấu ” đóng, nếu dòng tiếp theo là text không phải key:value / [ / ]
    #    thì xóa dòng đó đi
    raw = re.sub(
        r'("[^"\n]*")\s*\n\s*[\w\u00C0-\u024F\u1E00-\u1EFF][^":,{\[\]\n]*"?\s*(?=\n\s*[}\]])',
        r'\1',
        raw
    )

    return raw.strip()


def _recover_truncated_json(raw: str) -> str:
    """
    Cố gắng khắc phục JSON bị cắt ngang (Unterminated string / token limit).
    Đóng string hiện tại, rồi đóng các array/object chưa được đóng.
    """
    depth = 0
    in_string = False
    escape = False
    for ch in raw:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch in ('{', '['):
                depth += 1
            elif ch in ('}', ']'):
                depth -= 1

    recovery = raw.rstrip()
    if in_string:
        # Đóng string đang hở, thêm dấu ... để biểu thị bị cắt
        recovery += '...(bị cắt)"'

    # Đóng các mức lồng nhau còn lại
    while depth > 0:
        last = recovery.rstrip()
        if last.endswith('[') or last.endswith(','):
            recovery = last.rstrip(',') + ']'
        else:
            recovery += '}'
        depth -= 1

    return recovery


def call_gemini(slim: dict, api_key: str) -> dict:
    """
    Gọi Gemini API với slim payload.

    Args:
        slim   : dict từ build_slim_payload()
        api_key: Gemini API key (từ env GEMINI_API_KEY)

    Returns:
        dict kết quả phân tích từ Gemini (đã parse JSON)

    Raises:
        RuntimeError nếu API lỗi hoặc response không phải JSON hợp lệ
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError(
            "Thiếu thư viện google-genai. "
            "Chạy: pip install google-genai"
        )

    client = genai.Client(api_key=api_key)

    user_prompt = build_prompt(slim)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=3072,
            ),
        )
        raw_text = response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Gemini API lỗi: {e}") from e

    # Lớp 1: parse thẳng (trường hợp Gemini trả về JSON hợp lệ — phổ biến nhất)
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Lớp 2: làm sạch rồi parse (bỏ markdown fence, trailing comma)
    cleaned = _clean_json_text(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Lớp 3: tìm block {...} đầu tiên trong cleaned text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Lớp 4: json5 — parse liệt khoá hơn, xử lý được nhiều kiểu LLM output xấu
    try:
        import json5
        return json5.loads(cleaned)
    except Exception:
        pass

    # Lớp 5: recovery — đóng JSON bị cắt ngang do token limit
    try:
        recovered = _recover_truncated_json(cleaned)
        result = json.loads(recovered)
        # Đánh dấu response bị cắt để caller biết
        result.setdefault("_truncated", True)
        print("[WARNING] Gemini response bị cắt ngang (token limit). Đã phục hồi một phần.")
        return result
    except Exception:
        pass

    # Thất bại hoàn toàn — log đầy đủ để debug
    try:
        json.loads(raw_text)  # parse lại để lấy thông báo lỗi chính xác
    except json.JSONDecodeError as je:
        err_detail = f"dòng {je.lineno}, cột {je.colno}: {je.msg}"
    else:
        err_detail = "unknown"

    raise RuntimeError(
        f"Gemini trả về JSON không parse được ({err_detail}).\n"
        f"--- FULL RAW ({len(raw_text)} ký tự) ---\n{raw_text}"
    )






# ==============================================================================
# 4. ENRICHER — Ghép thông tin phụ từ final_json vào report
# ==============================================================================

def enrich_report(gemini_output: dict, final_json: dict, domain: str) -> dict:
    """
    Ghép thêm thông tin phụ từ final_json vào kết quả của Gemini.

    Những thông tin này không cần gửi cho Gemini (tốn token),
    nhưng cần có trong báo cáo cuối để người đọc hiểu context.

    Returns:
        dict báo cáo đầy đủ
    """
    # Lấy danh sách IP từ evidence
    resolved_ip = final_json.get("resolved_ip", [])

    # Lấy ASN summary
    asn_info = final_json.get("asn_info", {})
    asn_summary = {
        "asn":         asn_info.get("asn"),
        "description": asn_info.get("asn_description"),
        "country":     asn_info.get("country"),
    }

    # Redirect chain (giữ URL thôi, bỏ headers)
    redirect_history = final_json.get("redirect_history", [])
    redirect_chain = []
    for hop in redirect_history:
        if isinstance(hop, dict):
            url = hop.get("url") or hop.get("location")
            if url:
                redirect_chain.append(url)
        elif isinstance(hop, str):
            redirect_chain.append(hop)

    # NS records (nameservers — quan trọng cho suspicious hosting)
    dns_records = final_json.get("dns_records", {})
    ns_records  = dns_records.get("NS", [])

    # Thông tin domain cơ bản
    step0 = final_json.get("step0", {})

    report = {
        # ── Metadata ──
        "domain":           domain,
        "analyzed_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analyzer":         f"Gemini/{GEMINI_MODEL}",

        # ── Kết quả Gemini ──
        **gemini_output,

        # ── Thông tin phụ (enrich) ──
        "supplemental": {
            "input_domain":    step0.get("input_domain"),
            "normalized_domain": step0.get("normalized_domain"),
            "resolved_ips":    resolved_ip,
            "asn":             asn_summary,
            "ns_records":      ns_records,
            "redirect_chain":  redirect_chain,
            "registrar":       final_json.get("registrar"),
            "creation_date":   str(final_json.get("creation_date", "")),
            "domain_age_days": final_json.get("domain_age_days"),
            "cdn_providers":   final_json.get("cdn_providers", []),
        }
    }

    return report


# ==============================================================================
# 5. SAVE REPORT
# ==============================================================================

def save_report(report: dict, domain: str, timestamp: str, output_dir: str | None = None) -> str:
    """
    Lưu báo cáo vào output_dir/<safe_domain>_report_<timestamp>.json

    Args:
        output_dir : Thư mục đầu ra. Mặc định là logs/<domain>/
                     (cạnh file _final_).

    Returns:
        Đường dẫn file đã lưu
    """
    safe_domain = re.sub(r'[\\/*?"<>|]', "_", domain) if domain else "unknown"

    if output_dir is None:
        output_dir = os.path.join("logs", safe_domain)

    os.makedirs(output_dir, exist_ok=True)

    filename = f"{safe_domain}_report_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False, default=str)

    return filepath


# ==============================================================================
# 6. PUBLIC ENTRY POINT
# ==============================================================================

def run_step4(
    final_json: dict,
    api_key:    str,
    domain:     str | None = None,
    timestamp:  str | None = None,
    logs_dir:   str | None = None,
) -> dict:
    """
    Entry point cho Step 4 — Gemini Synthesis.

    Args:
        final_json : evidence_buffer đầy đủ từ Step 0-3
        api_key    : Gemini API key
        domain     : Tên domain (nếu None, tự suy ra từ final_json)
        timestamp  : Timestamp để đặt tên file (nếu None, tạo mới)
        logs_dir   : Thư mục lưu kết quả. Mặc định = logs/<domain>/
                     (cạnh file _final_ hiện tại)

    Returns:
        dict báo cáo đầy đủ (đã enrich)
    """
    if not api_key:
        raise ValueError(
            "Thiếu GEMINI_API_KEY. "
            "Set biến môi trường: set GEMINI_API_KEY=your_key_here"
        )

    # Suy ra domain nếu không có
    if not domain:
        domain = (
            final_json.get("step0", {}).get("normalized_domain")
            or "unknown"
        )

    if not timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n========================")
    print("STEP 4 — GEMINI SYNTHESIS")
    print("========================\n")

    # 1. Reducer
    print("[INFO] Đang rút gọn payload...")
    slim = build_slim_payload(final_json)
    print(f"[INFO] Slim payload: {len(json.dumps(slim, ensure_ascii=False))} ký tự")

    # 2. Gọi Gemini
    print(f"[INFO] Đang gọi Gemini API ({GEMINI_MODEL})...")
    try:
        gemini_output = call_gemini(slim, api_key)
        print(f"[INFO] Gemini trả về verdict: {gemini_output.get('verdict', '?')}")
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return {"error": str(e), "domain": domain}

    # 3. Enrich + gắn slim_payload vào report
    report = enrich_report(gemini_output, final_json, domain)
    report["input_summary"] = slim   # ← đầu vào rút gọn đã gửi Gemini

    # 4. Print summary
    verdict   = report.get("verdict", "?")
    confidence= report.get("confidence", 0)
    action    = report.get("recommended_action", "?")
    summary   = report.get("summary_vi", "")

    verdict_emoji = {
        "VI_PHAM":  "🚨",
        "NGHI_NGO": "⚠️",
        "AN_TOAN":  "✅",
    }.get(verdict, "❓")

    print(f"\n{verdict_emoji} Kết luận: {verdict} (confidence={confidence:.0%})")
    print(f"   Hành động đề xuất: {action}")
    if summary:
        print(f"   Tóm tắt: {summary}")

    violation_types = report.get("violation_types", [])
    if violation_types:
        print(f"   Loại vi phạm: {', '.join(violation_types)}")

    key_signals = report.get("key_signals", [])
    if key_signals:
        print("\n   Signals chính:")
        for s in key_signals:
            weight = s.get("weight", "?")
            signal = s.get("signal", "?")
            print(f"     [{weight}] {signal}")

    # 5. Save — vào logs_dir (cạnh file _final_)
    try:
        filepath = save_report(report, domain, timestamp, output_dir=logs_dir)
        print(f"\n[INFO] Báo cáo đã lưu vào: {filepath}")
    except Exception as e:
        print(f"[ERROR] Không thể lưu báo cáo: {e}")

    return report


# ==============================================================================
# STANDALONE RUNNER — python step4.py <path_to_final_json>
# ==============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step4.py <path_to_final_json>")
        print("  Ví dụ: python step4.py logs/example.com/example.com_final_20260705_120000.json")
        sys.exit(1)

    json_path = sys.argv[1]

    if not os.path.exists(json_path):
        print(f"[ERROR] File không tồn tại: {json_path}")
        sys.exit(1)

    # Đọc API key từ biến môi trường
    # api_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] Chưa set GEMINI_API_KEY.")
        print("  Windows: $env:GEMINI_API_KEY = 'your_key_here'")
        print("  Linux:   export GEMINI_API_KEY='your_key_here'")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Suy ra domain và timestamp từ tên file
    basename  = os.path.basename(json_path)
    parts     = basename.replace(".json", "").split("_")
    # Tên file dạng: <domain>_final_<YYYYMMDD>_<HHMMSS>.json
    # Lấy timestamp = 2 phần cuối
    ts_parts  = parts[-2:]
    timestamp = "_".join(ts_parts) if len(ts_parts) == 2 else datetime.now().strftime("%Y%m%d_%H%M%S")

    # Lưu report cạnh file _final_ (cùng thư mục)
    logs_dir = os.path.dirname(os.path.abspath(json_path))

    run_step4(data, api_key=api_key, timestamp=timestamp, logs_dir=logs_dir)
