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
    evidence_buffer["step2_evidence"] = step2_evidence

    print(
        json.dumps(
            step2_evidence,
            indent=4,
            ensure_ascii=False,
            default=str
        )
    )

    # Save combined output (Step 1 + Step 2)
    combined_file = f"{safe_domain}_full_{timestamp}.json"
    combined_path = os.path.join(logs_dir, combined_file)

    try:
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(
                evidence_buffer, f,
                indent=4, ensure_ascii=False, default=str
            )
        print(
            f"\n[INFO] Kết quả đầy đủ (Step 1 + Step 2) "
            f"đã lưu vào: {combined_path}"
        )
    except Exception as e:
        print(
            f"\n[ERROR] Không thể lưu file JSON kết quả: {e}"
        )

    # Save Step 2 separately as well
    step2_file = f"{safe_domain}_step2_{timestamp}.json"
    step2_path = os.path.join(logs_dir, step2_file)

    try:
        with open(step2_path, "w", encoding="utf-8") as f:
            json.dump(
                step2_evidence, f,
                indent=4, ensure_ascii=False, default=str
            )
        print(
            f"[INFO] Kết quả Step 2 riêng đã lưu vào: {step2_path}"
        )
    except Exception as e:
        print(
            f"[ERROR] Không thể lưu file JSON Step 2: {e}"
        )

    #################################################
    # STEP 3: AI/ML Evidence Engine
    # Branch 2: Content Model
    #################################################

    print("\n========================")
    print("STEP 3 — CONTENT MODEL")
    print("========================\n")

    dom_text = step2_evidence.get("dom_text", "")

    if dom_text:
        try:
            step3_evidence = run_content_model(dom_text)
            evidence_buffer["step3_evidence"] = step3_evidence

            print(
                json.dumps(
                    {k: v for k, v in step3_evidence.items()
                     if k != "segment_results"},  # Bỏ chi tiết segment khi in
                    indent=4,
                    ensure_ascii=False,
                    default=str,
                )
            )

            if step3_evidence["final_label"] == 1:
                print(
                    f"\n[ALERT] ⚠️ Content Model phát hiện NỘI DUNG ĐỘC HẠI!\n"
                    f"  Loại website: {step3_evidence['final_type_name']}\n"
                    f"  Xác suất cao nhất: {step3_evidence['max_malicious_prob']:.4f}\n"
                    f"  Số segment độc hại: {step3_evidence['malicious_segment_count']}"
                    f"/{step3_evidence['total_segments']}"
                )
            else:
                print(
                    f"\n[OK] Content Model: AN TOÀN\n"
                    f"  Loại website: {step3_evidence['final_type_name']}\n"
                    f"  Tổng segments: {step3_evidence['total_segments']}"
                )

        except Exception as e:
            print(f"\n[ERROR] Content Model lỗi: {e}")
            evidence_buffer["step3_evidence"] = {"error": str(e)}
    else:
        print("[WARN] Không có DOM text từ Step 2 — bỏ qua Content Model.")
        evidence_buffer["step3_evidence"] = {
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


if __name__ == "__main__":
    main()
