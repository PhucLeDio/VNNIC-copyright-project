# COPYRIGHT DETECTION SYSTEM — v1.0.4.1
# Chạy bình thường  : python main.py
# Cập nhật mô hình  : python main.py --update

import sys
import json
import os
import re
import msvcrt
from datetime import datetime

# Fix Unicode output trên Windows terminal (cp1252 không hỗ trợ tiếng Việt)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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
    print(" COPYRIGHT DETECTION SYSTEM v1.0.4.1")
    print("===================================\n")

    target_url = input(
        "Nhập domain hoặc URL cần kiểm tra: "
    ).strip()

    if not target_url:

        print("[ERROR] Domain không được để trống.")
        return

    # Tự động thêm https:// nếu đầu vào chưa có scheme (http/https)
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

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

    # ── Phát hiện redirect cross-domain từ Step 1 ──
    # Nếu requests bắt được redirect (ví dụ: animevietsub.id → animevietsub.meme),
    # cập nhật domain ngay trước khi tạo thư mục và lưu bất kỳ file nào.
    # Điều này đảm bảo TẤT CẢ log (step1, step2, step3, final, report) đều nằm
    # chung 1 thư mục theo domain đích — không bị tách ra 2 folder.
    _redirect_info = evidence_buffer.get("redirect_info", {})
    if _redirect_info.get("domain_hopping"):
        _domains_seen = _redirect_info.get("domains_seen", [])
        _final_domain = _domains_seen[-1] if _domains_seen else None
        if _final_domain and _final_domain != domain:
            print(
                f"\n[INFO] 🔀 Redirect cross-domain (Step 1): "
                f"{domain} → {_final_domain}\n"
                f"       Tất cả log sẽ được lưu vào thư mục: {_final_domain}/"
            )
            evidence_buffer["original_domain"] = domain   # lưu lại domain gốc
            domain = _final_domain
            # browser_url cũng cập nhật để Playwright mở thẳng domain đích
            redirect_history_urls = evidence_buffer.get("redirect_history", [])
            if redirect_history_urls:
                target_url = redirect_history_urls[-1]

    print(
        json.dumps(
            evidence_buffer,
            indent=4,
            ensure_ascii=False,
            default=str
        )
    )

    # Save Step 1 output to a JSON file inside a logs/v1.0.4.1/<domain> directory
    safe_domain = re.sub(r'[\\/*?:"<>|]', "_", domain) if domain else "unknown"
    logs_dir = os.path.join("logs", "v1.0.4.1", safe_domain)
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
    # Lưu ý: domain và target_url có thể đã được cập nhật theo redirect từ Step 1 ở trên
    browser_url = target_url
    if not browser_url.startswith("http"):
        browser_url = "https://" + browser_url

    step2_evidence = run_step2(domain, browser_url)

    # ── Fallback: cập nhật domain nếu Playwright phát hiện thêm redirect (JS / meta refresh) ──
    # Trường hợp này xảy ra khi redirect không bắt được qua requests (connection reset)
    # nhưng Playwright load được trang và thấy redirect phía browser.
    if step2_evidence.get("redirect_cross_domain"):
        redirected_domain = step2_evidence.get("target_domain", domain)
        if redirected_domain and redirected_domain != domain:
            print(
                f"\n[INFO] 🔀 Playwright phát hiện redirect bổ sung: "
                f"{domain} → {redirected_domain}\n"
                f"       Cập nhật thư mục log và nhãn domain theo URL thực."
            )
            domain = redirected_domain
            safe_domain = re.sub(r'[\\/*?:"<>|]', "_", domain)
            logs_dir = os.path.join("logs", "v1.0.4.1", safe_domain)
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)


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
    
    # Chỉ chạy OCR trên các banner có local_path (ảnh đã được YOLO xác nhận là betting và lưu lại)
    ad_banners = [b for b in banners if b.get("local_path")]

    if ad_banners:
        try:
            ocr_results = run_ocr_pipeline(
                ad_banners,
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
        print("[WARN] Không có banner betting hợp lệ để chạy OCR Engine.")
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


def ask_continue() -> bool:
    """Hỏi người dùng có muốn tiếp tục không.
    Nhấn Enter hoặc 'y'/'Y' để chạy lại.
    Nhấn ESC hoặc 'n'/'N' hoặc 'q'/'Q' để thoát.
    Trả về True nếu tiếp tục, False nếu thoát.
    """
    print("\n" + "=" * 43)
    print(" Nhấn  Enter  để kiểm tra domain tiếp theo")
    print(" Nhấn  ESC   để thoát chương trình")
    print("=" * 43)

    while True:
        key = msvcrt.getch()
        # ESC = 0x1B, Enter = 0x0D or 0x0A
        if key in (b'\x1b',):          # ESC
            return False
        if key in (b'\r', b'\n', b'y', b'Y'):  # Enter / y
            return True
        if key in (b'n', b'N', b'q', b'Q'):    # n / q
            return False
        # Mọi phím khác: bỏ qua, chờ tiếp


if __name__ == "__main__":
    # Kiểm tra nếu người dùng muốn cập nhật mô hình từ Hugging Face
    if "--update" in sys.argv:
        print("\n==========================================")
        print("[INFO] Bắt đầu kiểm tra và cập nhật mô hình...")
        print("==========================================\n")
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model"))
            from model_loader import get_domain_model, get_content_model
            get_domain_model(force_update=True)
            get_content_model(force_update=True)
            print("\n[SUCCESS] Cập nhật thành công các mô hình mới nhất từ Hugging Face!")
            print("[INFO] Từ lần chạy sau, bạn có thể chạy bình thường không cần `--update` để load offline tốc độ tối đa.\n")
        except Exception as e:
            print(f"\n[ERROR] Lỗi khi cập nhật mô hình: {e}")
        sys.exit(0)

    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("\n\n[INFO] Đã nhận Ctrl+C — thoát chương trình.")
            break
        except Exception as e:
            print(f"\n[ERROR] Lỗi không mong đợi: {e}")

        if not ask_continue():
            print("\n[INFO] Thoát chương trình. Tạm biệt!\n")
            break
