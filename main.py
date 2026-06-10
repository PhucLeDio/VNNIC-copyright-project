# main.py

import json
import os
import re
from datetime import datetime

from step0 import (
    normalize_domain,
    check_domain_in_database
)

from evidence import (
    build_evidence_buffer
)

from step2 import run_step2

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

    print(
        json.dumps(
            evidence_buffer,
            indent=4,
            ensure_ascii=False,
            default=str
        )
    )

    # Save Step 1 output to a JSON file inside a logs/ directory
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_domain = re.sub(r'[\\/*?:"<>|]', "_", domain) if domain else "unknown"
    log_file_name = f"{safe_domain}_step1_{timestamp}.json"
    log_file_path = os.path.join(logs_dir, log_file_name)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            json.dump(evidence_buffer, f, indent=4, ensure_ascii=False, default=str)
        print(f"\n[INFO] Kết quả Step 1 đã được lưu vào file JSON: {log_file_path}")
    except Exception as e:
        print(f"\n[ERROR] Không thể lưu file JSON kết quả Step 1: {e}")


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


if __name__ == "__main__":
    main()
