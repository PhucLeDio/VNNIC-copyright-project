# streamlit.exe run app.py

import os
import json
import glob
from PIL import Image
import streamlit as st
import pandas as pd

# Set page config for a wide layout and clean browser tab title
st.set_page_config(
    page_title="Hệ Thống Giám Sát Bản Quyền & Quảng Cáo",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injected Custom CSS for premium styling (sleek elements, badges, hover animations, and clean cards)
st.markdown("""
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Custom badge styles */
    .verdict-badge {
        display: inline-block;
        padding: 6px 16px;
        font-size: 16px;
        font-weight: 600;
        border-radius: 30px;
        text-align: center;
        margin-bottom: 10px;
    }
    .verdict-vi-pham {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .verdict-an-toan {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .verdict-other {
        background-color: rgba(107, 114, 128, 0.15);
        color: #6b7280;
        border: 1px solid rgba(107, 114, 128, 0.3);
    }
    
    /* Custom cards styling */
    .metric-card {
        background-color: #1e293b;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 4px;
    }
    .metric-label {
        font-size: 13px;
        font-weight: 500;
        color: #94a3b8;
    }
    
    /* Signal cards */
    .signal-card {
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 5px solid;
    }
    .signal-high {
        background-color: rgba(239, 68, 68, 0.05);
        border-left-color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.1);
        border-left-width: 5px;
    }
    .signal-medium {
        background-color: rgba(245, 158, 11, 0.05);
        border-left-color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.1);
        border-left-width: 5px;
    }
    .signal-low {
        background-color: rgba(59, 130, 246, 0.05);
        border-left-color: #3b82f6;
        border: 1px solid rgba(59, 130, 246, 0.1);
        border-left-width: 5px;
    }
    
    /* Evidence image wrapper */
    .evidence-card {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 15px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .evidence-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        border-color: #475569;
    }
    
    /* Clean links */
    a.custom-link {
        color: #38bdf8 !important;
        text-decoration: none;
        font-weight: 500;
    }
    a.custom-link:hover {
        text-decoration: underline;
    }
</style>
""", unsafe_allow_html=True)


def scan_reports(base_dir=os.path.join("logs", "v1.0.5")):
    """
    Scans base_dir for files ending with _report_*.json
    and maps them to their respective _final_*.json files.
    """
    reports = []
    # Search all folders in current directory, ignore env/venv
    pattern = os.path.join(base_dir, "**", "*_report_*.json")
    for file_path in glob.glob(pattern, recursive=True):
        # Ignore files inside venv
        if "venv" in file_path or ".git" in file_path or ".gemini" in file_path:
            continue
            
        file_name = os.path.basename(file_path)
        directory = os.path.dirname(file_path)
        
        # Try to locate corresponding final.json file
        final_file_name = file_name.replace("_report_", "_final_")
        final_file_path = os.path.join(directory, final_file_name)
        
        if not os.path.exists(final_file_path):
            # Try to search for any other final files if naming format differs slightly
            domain_part = file_name.split("_report_")[0]
            final_files = glob.glob(os.path.join(directory, f"{domain_part}_final_*.json"))
            if final_files:
                final_file_path = final_files[0]
            else:
                final_file_path = None
                
        reports.append({
            "report_path": file_path,
            "final_path": final_file_path,
            "filename": file_name,
            "domain": file_name.split("_report_")[0],
            "dir": directory
        })
    return sorted(reports, key=lambda x: x["domain"])


def load_json(filepath):
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Lỗi khi đọc file JSON {filepath}: {e}")
        return None


# App header
st.title("🛡️ Copyright & OCR Violation Inspector")
st.markdown("Hệ thống phân tích hạ tầng website lậu, vi phạm bản quyền và quảng cáo cờ bạc, cá độ trái phép.")
st.markdown("---")

# Scan files
reports_list = scan_reports()

if not reports_list:
    st.warning("⚠️ Không tìm thấy file báo cáo `_report_*.json` nào trong thư mục hiện tại.")
    st.info("Hãy đảm bảo bạn đặt các file JSON kết quả quét trong cùng thư mục dự án này.")
else:
    # Sidebar control
    st.sidebar.title("🔍 Quản Lý Báo Cáo")
    
    # Selection of reports
    report_options = {f"{r['domain']} ({os.path.basename(r['report_path']).split('_report_')[1][:8]})": r for r in reports_list}
    selected_key = st.sidebar.selectbox("Chọn tên miền báo cáo:", list(report_options.keys()))
    selected_report = report_options[selected_key]
    
    # Load selected data
    report_data = load_json(selected_report["report_path"])
    final_data = load_json(selected_report["final_path"])
    
    if report_data:
        domain = report_data.get("domain") or selected_report["domain"]
        verdict = report_data.get("verdict") or "N/A"
        confidence = report_data.get("confidence") or 0.0
        analyzed_at = report_data.get("analyzed_at") or "N/A"
        violation_types = report_data.get("violation_types") or []
        rec_action = report_data.get("recommended_action") or "N/A"
        
        # Sidebar Summary Stats
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Thông Tin Nhanh")
        
        # Style verdict
        if verdict == "VI_PHAM":
            st.sidebar.markdown(f'<div class="verdict-badge verdict-vi-pham">🔴 VI PHẠM</div>', unsafe_allow_html=True)
        elif verdict == "AN_TOAN":
            st.sidebar.markdown(f'<div class="verdict-badge verdict-an-toan">🟢 AN TOÀN</div>', unsafe_allow_html=True)
        else:
            st.sidebar.markdown(f'<div class="verdict-badge verdict-other">⚪ {verdict}</div>', unsafe_allow_html=True)
            
        st.sidebar.metric("Độ tin cậy (Confidence)", f"{confidence * 100:.1f}%")
        st.sidebar.write(f"**Thời gian quét:** {analyzed_at}")
        st.sidebar.write(f"**Hành động:** `{rec_action}`")
        
        # Input statistics
        input_summary = report_data.get("input_summary") or {}
        ocr_banner_count = input_summary.get("ocr_banner_count") or 0
        ocr_flagged_count = input_summary.get("ocr_flagged_count") or 0
        
        st.sidebar.write(f"**Tổng số banner phát hiện:** {ocr_banner_count}")
        st.sidebar.write(f"**Số banner vi phạm (OCR):** {ocr_flagged_count}")
        
        # Main Dashboard Layout
        # Row 1: Domain Header and Main Metrics
        col_header, col_metrics = st.columns([2, 1])
        
        with col_header:
            st.subheader(f"🌐 Báo Cáo Phân Tích: {domain}")
            
            # Big verdict banner
            if verdict == "VI_PHAM":
                st.error(f"🚨 **PHÁN QUYẾT: VI PHẠM BẢN QUYỀN & QUẢNG CÁO TRÁI PHÉP** (Hành động khuyến nghị: {rec_action})")
            elif verdict == "AN_TOAN":
                st.success(f"✅ **PHÁN QUYẾT: HỆ THỐNG GHI NHẬN AN TOÀN** (Hành động khuyến nghị: {rec_action})")
            else:
                st.info(f"ℹ️ **PHÁN QUYẾT: {verdict}** (Hành động khuyến nghị: {rec_action})")
                
            st.markdown(f"**Tóm tắt nội dung vi phạm:**")
            st.info(report_data.get("summary_vi", "Không có tóm tắt tiếng Việt."))
            
        with col_metrics:
            # Displays metric cards using HTML
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 10px;">
                <div class="metric-card">
                    <div class="metric-label">Độ Tin Cậy</div>
                    <div class="metric-value">{confidence * 100:.0f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Điểm Rủi Ro</div>
                    <div class="metric-value" style="color: #f59e0b;">{input_summary.get('risk_score', 'N/A')}</div>
                </div>
                <div class="metric-card" style="grid-column: span 2;">
                    <div class="metric-label">Tỷ lệ Banner Vi Phạm (OCR)</div>
                    <div class="metric-value" style="color: #ef4444;">{ocr_flagged_count} / {ocr_banner_count}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        
        # Row 2: Violation details & Key Signals
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("⚠️ Các Tín Hiệu Phát Hiện Vấn Đề")
            key_signals = report_data.get("key_signals") or []
            
            if not key_signals:
                st.write("Không phát hiện tín hiệu bất thường nào.")
            else:
                for sig in key_signals:
                    weight = sig.get("weight", "MEDIUM")
                    layer = sig.get("layer", "N/A")
                    signal_text = sig.get("signal", "")
                    
                    # Choose color based on weight
                    card_class = "signal-low"
                    emoji = "🔵"
                    if weight == "HIGH":
                        card_class = "signal-high"
                        emoji = "🔴"
                    elif weight == "MEDIUM":
                        card_class = "signal-medium"
                        emoji = "🟡"
                        
                    st.markdown(f"""
                    <div class="signal-card {card_class}">
                        <strong>{emoji} [{weight} SEVERITY] - Tầng {layer}</strong><br/>
                        {signal_text}
                    </div>
                    """, unsafe_allow_html=True)
                    
        with col_right:
            st.subheader("🔍 Phân Loại Hành Vi Vi Phạm")
            if not violation_types:
                st.write("Không ghi nhận phân loại vi phạm cụ thể.")
            else:
                for vt in violation_types:
                    st.markdown(f"- **{vt}**")
            
            st.subheader("💡 Ghi chú phân tích hệ thống")
            st.markdown(f"*{report_data.get('analysis_note', 'Không có ghi chú phân tích.')}*")
            
            # Domain and Hosting Info Summary
            supplemental = report_data.get("supplemental") or {}
            if supplemental:
                st.markdown("##### 📁 Tóm tắt hạ tầng:")
                infra_df = pd.DataFrame([
                    {"Thông số": "TLD", "Giá trị": input_summary.get("tld", "N/A")},
                    {"Thông số": "CDN Sử dụng", "Giá trị": ", ".join(supplemental.get("cdn_providers") or []) or "None"},
                    {"Thông số": "ASN Hosting", "Giá trị": (supplemental.get("asn") or {}).get("description", "N/A")},
                    {"Thông số": "Mail Provider", "Giá trị": input_summary.get("mail_provider", "Không sử dụng") or "Không sử dụng"}
                ])
                st.dataframe(infra_df, hide_index=True, width='stretch')

        st.markdown("---")
        
        # Row 3: Banner Detections (Evidence)
        st.subheader("📸 Banner Bằng Chứng Vi Phạm (Vi phạm OCR phát hiện)")
        
        # Extract matched banners from final JSON
        flagged_banners = []
        if final_data:
            step3_evidence = final_data.get("step3_evidence") or {}
            branch1_ocr = step3_evidence.get("branch1_ocr") or {}
            ocr_results = branch1_ocr.get("results") or []
            
            # Filter results where matched is True
            flagged_banners = [b for b in ocr_results if b.get("matched") is True]
            
        # Fallback if no final data or no matched banners, but report says there are flagged banners
        if not flagged_banners:
            if ocr_flagged_count > 0:
                # Let's search standard banner data if available
                st.warning("⚠️ Không tìm thấy bằng chứng banner vi phạm cụ thể trong file final.json hoặc file final.json thiếu thông tin chi tiết OCR.")
            # Let's display whatever banners we can find as evidence, limiting to the flagged count
            if final_data and final_data.get("step2_evidence"):
                banners = final_data["step2_evidence"].get("banners") or []
                if ocr_flagged_count > 0:
                    st.info(f"Đang hiển thị {min(ocr_flagged_count, len(banners))} banner lấy ngẫu nhiên làm bằng chứng từ danh sách thu thập được.")
                flagged_banners = banners[:ocr_flagged_count]
                
        if flagged_banners:
            st.markdown(f"Đã trích xuất **{len(flagged_banners)}** banner vi phạm được ghi nhận làm bằng chứng kỹ thuật:")
            
            # Display banner images in columns
            cols = st.columns(2)
            for idx, banner in enumerate(flagged_banners):
                col = cols[idx % 2]
                with col:
                    st.markdown('<div class="evidence-card">', unsafe_allow_html=True)
                    
                    # Resolve path of image
                    json_path = banner.get("path") or banner.get("local_path")
                    img_loaded = False
                    
                    if json_path:
                        filename = os.path.basename(json_path)
                        # Reconstruct local path relative to report file directory
                        local_path = os.path.join(selected_report["dir"], "banners", filename)
                        
                        if os.path.exists(local_path):
                            try:
                                img = Image.open(local_path)
                                st.image(img, caption=f"Banner #{idx+1}: {banner.get('alt', 'No alt text')}", width='stretch')
                                img_loaded = True
                            except Exception as img_err:
                                st.warning(f"Không thể load ảnh cục bộ: {img_err}")
                                
                    # Fallback to source URL if not loaded and source URL is available
                    if not img_loaded and banner.get("src_url"):
                        try:
                            st.image(banner.get("src_url"), caption=f"Banner #{idx+1} (Tải từ URL gốc): {banner.get('alt', 'No alt')}", width='stretch')
                            img_loaded = True
                        except Exception:
                            pass
                            
                    if not img_loaded:
                        st.error(f"❌ Không tìm thấy file banner cục bộ và không tải được từ URL gốc.")
                        st.code(f"Đường dẫn file: {json_path}\nURL gốc: {banner.get('src_url')}")
                        
                    # Banner details
                    st.markdown(f"**🎯 Phân nhóm:** <span style='color: #ef4444; font-weight:600;'>{banner.get('field', 'Cờ bạc')}</span>", unsafe_allow_html=True)
                    st.markdown(f"**🔑 Từ khóa vi phạm phát hiện:** `{banner.get('keyword', 'N/A')}`")
                    
                    # Destination Links
                    href = banner.get("link_href")
                    if href:
                        st.markdown(f"**🔗 Trang đích liên kết:** <a href='{href}' target='_blank' class='custom-link'>{href}</a>", unsafe_allow_html=True)
                    else:
                        st.markdown("**🔗 Trang đích liên kết:** Không phát hiện")
                        
                    # OCR text detail
                    ocr_text = banner.get("ocr_raw") or banner.get("ocr_norm")
                    if ocr_text:
                        with st.expander("📝 Chi tiết văn bản nhận dạng OCR"):
                            st.write(ocr_text)
                            
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Không có hình ảnh banner vi phạm được trích xuất.")
            
        st.markdown("---")
        
        # Tabs for technical detail
        st.subheader("⚙️ Thông Tin Phân Tích Kỹ Thuật Chi Tiết")
        tab_infra, tab_redirects, tab_all_banners, tab_raw = st.tabs([
            "🖥️ Hạ Tầng & DNS",
            "🔄 Chuỗi Chuyển Hướng",
            "🖼️ Tất Cả Banner Thu Thập",
            "📄 Dữ Liệu Raw JSON"
        ])
        
        with tab_infra:
            col_inf_left, col_inf_right = st.columns(2)
            with col_inf_left:
                st.markdown("#### Bản ghi DNS")
                if final_data and final_data.get("dns_records"):
                    dns = final_data["dns_records"]
                    for record_type, records in dns.items():
                        if records:
                            st.write(f"**Bản ghi {record_type}:**")
                            st.code("\n".join(records))
                else:
                    # Fallback to report supplemental records
                    st.write(f"**IP phân giải:** {', '.join(supplemental.get('resolved_ips') or [])}")
                    st.write(f"**NS Records:**")
                    st.code("\n".join(supplemental.get("ns_records") or []))
            
            with col_inf_right:
                st.markdown("#### Thông tin Máy Chủ & HTTP Headers")
                if final_data and final_data.get("http_headers"):
                    st.json(final_data["http_headers"])
                else:
                    st.write("Không tìm thấy thông tin http_headers trong file final.")
                    
                st.markdown("#### Tín Hiệu Hợp Lệ (Legitimate Signals)")
                if final_data and final_data.get("legitimate_signals"):
                    ls = final_data["legitimate_signals"]
                    ls_df = pd.DataFrame([
                        {"Tín hiệu": k, "Trạng thái": "✅ Có" if v else "❌ Không"}
                        for k, v in ls.items() if k != "total_signals"
                    ])
                    st.dataframe(ls_df, hide_index=True, width='stretch')
                    
        with tab_redirects:
            st.markdown("#### Lịch sử chuyển hướng tên miền")
            redirects = supplemental.get("redirect_chain") or []
            if not redirects and final_data:
                redirects = final_data.get("redirect_history") or []
                
            if redirects:
                for i, url in enumerate(redirects):
                    st.markdown(f"**Bước {i+1}:** `{url}`")
                
                # Check domain hopping
                if final_data and final_data.get("redirect_info"):
                    info = final_data["redirect_info"]
                    st.write(f"**Độ sâu chuyển hướng (Depth):** {info.get('redirect_depth')}")
                    st.write(f"**Domain Hopping:** {'⚠️ Có hiện tượng nhảy tên miền liên tục' if info.get('domain_hopping') else 'Không'}")
            else:
                st.info("Không phát hiện chuỗi chuyển hướng.")
                
        with tab_all_banners:
            st.markdown("#### Tổng hợp tất cả banner đã thu thập từ website")
            if final_data and final_data.get("step2_evidence"):
                all_banners = final_data["step2_evidence"].get("banners") or []
                st.write(f"Tổng số banner quét được trên giao diện: **{len(all_banners)}**")
                
                # Render a summary table of all banners
                banners_summary = []
                for idx, b in enumerate(all_banners):
                    # Check matched status from branch1_ocr if exists
                    matched_status = "Bình thường"
                    keyword_hit = "-"
                    category_hit = "-"
                    
                    if final_data:
                        step3_evidence = final_data.get("step3_evidence") or {}
                        branch1_ocr = step3_evidence.get("branch1_ocr") or {}
                        ocr_results = branch1_ocr.get("results") or []
                        for ocr_b in ocr_results:
                            ocr_path = ocr_b.get("path") or ocr_b.get("local_path")
                            banner_path = b.get("local_path") or b.get("path")
                            has_matching_url = ocr_b.get("src_url") and b.get("src_url") and ocr_b.get("src_url") == b.get("src_url")
                            has_matching_path = ocr_path and banner_path and os.path.basename(ocr_path) == os.path.basename(banner_path)
                            
                            if has_matching_url or has_matching_path:
                                if ocr_b.get("matched"):
                                    matched_status = "⚠️ Vi phạm"
                                    keyword_hit = ocr_b.get("keyword", "-")
                                    category_hit = ocr_b.get("field", "-")
                                break
                                
                    banners_summary.append({
                        "STT": idx + 1,
                        "Alt Text": b.get("alt", ""),
                        "Kích Thước": f"{b.get('width')}x{b.get('height')}",
                        "Trạng Thái": matched_status,
                        "Phân loại": category_hit,
                        "Từ khóa vi phạm": keyword_hit,
                        "Link URL": b.get("link_href", "")
                    })
                
                if banners_summary:
                    st.dataframe(pd.DataFrame(banners_summary), hide_index=True, width='stretch')
            else:
                st.info("Không có thông tin về tất cả banner.")
                
        with tab_raw:
            st.markdown("#### Chi tiết cấu trúc dữ liệu JSON Báo cáo và Dữ liệu cuối cùng")
            col_raw_l, col_raw_r = st.columns(2)
            with col_raw_l:
                st.write("**Report JSON (`_report.json`)**")
                st.json(report_data)
            with col_raw_r:
                st.write("**Final JSON (`_final.json`)**")
                if final_data:
                    st.json(final_data)
                else:
                    st.warning("Không có dữ liệu final JSON.")
    else:
        st.error("Không thể load được dữ liệu báo cáo.")
