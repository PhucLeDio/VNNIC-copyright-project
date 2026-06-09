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


if __name__ == "__main__":
    main()
