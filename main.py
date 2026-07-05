# main.py

import json
import os
import re
from datetime import datetime

from step0 import (
    normalize_domain,
    check_domain_in_database,
    run_domain_model_check,
)

from evidence import (
    build_evidence_buffer
)

from step2 import run_step2
from step3 import run_content_model
from ocr_banner import run_ocr_pipeline
from step4 import run_step4

#################################################
# CONFIG
#################################################

CSV_PATH = "danh_sach_domain_whitelist.csv"


#################################################
# MAIN
#################################################

def main():

    print("\n===================================")
    print(" COPYRIGHT DETECTION SYSTEM ")
    print("===================================\n")

    target_url = input(
        "Nhập domain hoặc URL cần kiểm tra: "
    ).strip()

    if not target_url:

        print("[ERROR] Domain không được để trống.")
        return

    domain = normalize_domain(
        target_url
    )

    print("\n========================")
    print("STEP 0")
    print("========================\n")

    step0_result = check_domain_in_database(
        target_url,
        CSV_PATH
    )

    print(
        json.dumps(
            step0_result,
            indent=4,
            ensure_ascii=False
        )
    )

    if step0_result["in_database"]:

        print(
            "\n[INFO] Domain nằm trong whitelist. Vẫn tiếp tục phân tích để kiểm tra dấu hiệu bất thường..."
        )

    #################################################
    # STEP 1
    #################################################

    print("\n========================")
    print("STEP 1")
    print("========================\n")

    evidence_buffer = build_evidence_buffer(
        domain,
        target_url
    )

    evidence_buffer["step0"] = step0_result

    print(
        json.dumps(
            evidence_buffer,
            indent=4,
            ensure_ascii=False,
            default=str
        )
    )

    # Save Step 1 output to a JSON file inside a logs/<domain> directory
    safe_domain = re.sub(r'[\\/*?:"<>|]', "_", domain) if domain else "unknown"
    logs_dir = os.path.join("logs", safe_domain)
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_name = f"{safe_domain}_step1_{timestamp}.json"
    log_file_path = os.path.join(logs_dir, log_file_name)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            json.dump(evidence_buffer, f, indent=4, ensure_ascii=False, default=str)
        print(f"\n[INFO] Kết quả Step 1 đã được lưu vào file JSON: {log_file_path}")
    except Exception as e:
        print(f"\n[ERROR] Không thể lưu file JSON kết quả Step 1: {e}")

    #################################################
    # STEP 0 PART 2: Domain Model
    # (chạy sau Step 1 vì cần DNS/IP data để tính features)
    #################################################

    print("\n========================")
    print("STEP 0 — DOMAIN MODEL")
    print("========================\n")

    try:
        domain_model_result = run_domain_model_check(
            domain,
            step1_evidence=evidence_buffer
        )
        evidence_buffer["step0"]["domain_model"] = domain_model_result
        print(
            json.dumps(
                domain_model_result,
                indent=4,
                ensure_ascii=False,
            )
        )
        if domain_model_result["flag"] == "FLAG_DOMAIN_PREDICT_MALICIOUS":
            print("\n[ALERT] ⚠️ Domain Model dự đoán domain ĐỘC HẠI!")
    except Exception as e:
        print(f"\n[ERROR] Domain Model lỗi: {e}")
        evidence_buffer["step0"]["domain_model"] = {"error": str(e)}


    #################################################
    # STEP 2: Deep Browser Evidence Collection
    #################################################

    print("\n========================")
    print("STEP 2")
    print("========================\n")

    # Ensure URL has scheme for Playwright
    browser_url = target_url
    if not browser_url.startswith("http"):
        browser_url = "https://" + browser_url

    step2_evidence = run_step2(domain, browser_url)

    # Merge Step 2 into the evidence buffer
    # step2_evidence chỉ chứa dữ liệu thu thập thô (banners, dom_text, streams...)
    # Kết quả phân tích (OCR, Content Model) được lưu riêng vào step3_evidence
    evidence_buffer["step2_evidence"] = step2_evidence

    print(
        json.dumps(
            # In step2 không bao gồm banners (quá dài) — chỉ in các field tóm tắt
            {k: v for k, v in step2_evidence.items()
             if k not in ("banners", "dom_text", "banner_network_hits")},
            indent=4,
            ensure_ascii=False,
            default=str
        )
    )

    # Save Step 2 separately (chưa có OCR — chỉ dữ liệu thu thập thô)
    step2_file = f"{safe_domain}_step2_{timestamp}.json"
    step2_path = os.path.join(logs_dir, step2_file)

    try:
        with open(step2_path, "w", encoding="utf-8") as f:
            json.dump(
                step2_evidence, f,
                indent=4, ensure_ascii=False, default=str
            )
        print(
            f"[INFO] Kết quả Step 2 đã lưu vào: {step2_path}"
        )
    except Exception as e:
        print(
            f"[ERROR] Không thể lưu file JSON Step 2: {e}"
        )

    #################################################
    # STEP 3: AI/ML Evidence Engine
    # Branch 1: OCR Engine (Banner Analysis)
    # Branch 2: Content Model (DOM Text)
    # Kết quả được tổng hợp vào evidence_buffer["step3_evidence"]
    #################################################

    # Khởi tạo step3_evidence với cấu trúc 2 branch
    evidence_buffer["step3_evidence"] = {
        "branch1_ocr":           None,   # sẽ được điền bởng OCR Engine
        "branch2_content_model": None,   # sẽ được điền bởng Content Model
    }

    # ── Branch 1: OCR Engine ──
    print("\n========================")
    print("STEP 3 — BRANCH 1: OCR ENGINE")
    print("========================\n")

    banners = step2_evidence.get("banners", [])
    if banners:
        try:
            ocr_results = run_ocr_pipeline(
                banners,
                keywords_csv="keywords/Keywords_v1.csv",
            )
            flagged = [r for r in ocr_results if r.get("matched")]
            total   = len(ocr_results)

            evidence_buffer["step3_evidence"]["branch1_ocr"] = {
                "banner_count":   total,
                "flagged_count":  len(flagged),
                "has_gambling_banner": len(flagged) > 0,
                "results":        ocr_results,
            }

            if flagged:
                print(
                    f"\n[ALERT] ⚠️  Phát hiện {len(flagged)}/{total} banner "
                    f"có dấu hiệu cờ bạc / cá độ!"
                )
                for r in flagged:
                    tier      = r.get("tier_hit", "?")
                    kw        = r.get("keyword", "?")
                    score     = r.get("score")
                    score_str = f"{score:.2f}" if score is not None else "N/A"
                    path      = os.path.basename(r.get("path") or r.get("src_url") or "?")
                    field     = r.get("field", "?")
                    print(
                        f"  [T{tier}] '{kw}' "
                        f"| field={field} "
                        f"| score={score_str} "
                        f"| file={path}"
                    )
            else:
                print(
                    f"[OK] OCR Engine: Không phát hiện banner cờ bạc "
                    f"({total} banner đã kiểm tra)"
                )

        except Exception as e:
            print(f"\n[ERROR] OCR Engine lỗi: {e}")
            evidence_buffer["step3_evidence"]["branch1_ocr"] = {"error": str(e)}
    else:
        print("[WARN] Không có banner từ Step 2 — bỏ qua OCR Engine.")
        evidence_buffer["step3_evidence"]["branch1_ocr"] = {
            "banner_count": 0, "flagged_count": 0,
            "has_gambling_banner": False, "results": [],
        }

    # ── Branch 2: Content Model ──
    print("\n========================")
    print("STEP 3 — BRANCH 2: CONTENT MODEL")
    print("========================\n")

    dom_text = step2_evidence.get("dom_text", "")

    if dom_text:
        try:
            content_result = run_content_model(dom_text)
            evidence_buffer["step3_evidence"]["branch2_content_model"] = content_result

            print(
                json.dumps(
                    {k: v for k, v in content_result.items()
                     if k != "segment_results"},
                    indent=4,
                    ensure_ascii=False,
                    default=str,
                )
            )

            if content_result["final_label"] == 1:
                print(
                    f"\n[ALERT] ⚠️ Content Model phát hiện NỘI DUNG ĐỘC HẠI!\n"
                    f"  Loại website: {content_result['final_type_name']}\n"
                    f"  Xác suất cao nhất: {content_result['max_malicious_prob']:.4f}\n"
                    f"  Số segment độc hại: {content_result['malicious_segment_count']}"
                    f"/{content_result['total_segments']}"
                )
            else:
                print(
                    f"\n[OK] Content Model: AN TOÀN\n"
                    f"  Loại website: {content_result['final_type_name']}\n"
                    f"  Tổng segments: {content_result['total_segments']}"
                )

        except Exception as e:
            print(f"\n[ERROR] Content Model lỗi: {e}")
            evidence_buffer["step3_evidence"]["branch2_content_model"] = {"error": str(e)}
    else:
        print("[WARN] Không có DOM text từ Step 2 — bỏ qua Content Model.")
        evidence_buffer["step3_evidence"]["branch2_content_model"] = {
            "note": "Không có DOM text từ Step 2.",
            "final_label": None,
        }

    # Save final combined output (Step 1 + Step 2 + Step 3)
    final_file = f"{safe_domain}_final_{timestamp}.json"
    final_path = os.path.join(logs_dir, final_file)

    try:
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(
                evidence_buffer, f,
                indent=4, ensure_ascii=False, default=str
            )
        print(
            f"\n[INFO] Kết quả đầy đủ (Step 1 + Step 2 + Step 3) "
            f"đã lưu vào: {final_path}"
        )
    except Exception as e:
        print(
            f"\n[ERROR] Không thể lưu file JSON kết quả cuối: {e}"
        )

    #################################################
    # STEP 4: Gemini API Synthesis
    #################################################

    print("\n========================")
    print("STEP 4")
    print("========================\n")

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    if not gemini_api_key:
        print(
            "[WARN] Biến môi trường GEMINI_API_KEY chưa được set.\n"
            "       Bỏ qua Step 4. Để chạy sau:\n"
            "         Windows: $env:GEMINI_API_KEY = 'your_key'\n"
            "         Linux  : export GEMINI_API_KEY='your_key'\n"
            f"         Sau đó: python step4.py {final_path}"
        )
    else:
        try:
            run_step4(
                evidence_buffer,
                api_key=gemini_api_key,
                domain=domain,
                timestamp=timestamp,
                logs_dir=logs_dir,   # lưu cạnh file _final_
            )
        except Exception as e:
            print(f"\n[ERROR] Step 4 lỗi: {e}")


if __name__ == "__main__":
    main()
