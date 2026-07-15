# Tài liệu Kỹ thuật: Luồng Xử lý Phát hiện Vi phạm Bản quyền Số (Flow v4.1)

Tài liệu này mô tả chi tiết toàn bộ quy trình hoạt động của đường ống phân tích (pipeline) phát hiện vi phạm sở hữu trí tuệ (SHTT) và bản quyền số trên Internet, được xây dựng dựa trên thiết kế **Flow v4.1**.

Hệ thống hoạt động theo mô hình kiểm tra đa lớp kết hợp giữa phân tích hạ tầng mạng, mô phỏng trình duyệt, thị giác máy tính (Computer Vision), xử lý ngôn ngữ tự nhiên (NLP) và trí tuệ nhân tạo tổng hợp (Generative AI - LLM) để đưa ra bằng chứng pháp lý vững chắc.

---

## 1. Sơ đồ Luồng Xử lý Tổng quan (Flow Architecture)

Dưới đây là sơ đồ luồng dữ liệu đi qua 5 bước (từ Step 0 đến Step 4) của hệ thống:

```mermaid
graph TD
    A[Bắt đầu: Nhập URL nghi vấn] --> Step0[Step 0: Whitelist & Domain Model]
    
    subgraph Step0_Detail [Step 0: Whitelist & Sơ bộ Tên miền]
        Step0 --> S0_1[Tra cứu Whitelist VNNIC]
        Step0 --> S0_2[Trích xuất 12 Đặc trưng Lexical]
        S0_2 --> S0_3[Phân loại sơ bộ bằng PhoBERT Domain Model]
    end

    Step0 --> Step1[Step 1: Network Intelligence & Redirect Tracking]
    
    subgraph Step1_Detail [Step 1: Thông tin Mạng & Hạ tầng]
        Step1 --> S1_1[WHOIS: Tuổi domain, Registrar Risk, Quyền riêng tư]
        Step1 --> S1_2[DNS Records: Phân giải A, NS, MX, TXT]
        Step1 --> S1_3[Redirect Chain: Theo dõi nhảy tên miền - Domain Hopping]
        Step1 --> S1_4[Nhận diện Hosting: Cloud Provider vs Suspicious Host]
        Step1 --> S1_5[Tính điểm: Risk Score & Legitimacy Score]
    end

    Step1 --> Step2[Step 2: Deep Browser Evidence Collection]
    
    subgraph Step2_Detail [Step 2: Mô phỏng Browser & Thu thập Sâu]
        Step2 --> S2_1[Khởi tạo Playwright Stealth Browser để vượt Cloudflare]
        Step2 --> S2_2[Crawl Watch/Episode Pages theo Regex Pattern]
        Step2 --> S2_3[Tự động chặn Pop-up / Ad Tabs]
        Step2 --> S2_4[Trích xuất DOM Text & Chụp ảnh giao diện]
        Step2 --> S2_5[Đánh chặn Network: Phát hiện Stream .m3u8, .mp4, Iframe players]
        Step2 --> S2_6[Quét Footer Pháp lý: MST, Giấy phép, DMCA, Telegram]
    end

    Step2 --> Step3[Step 3: Phân tích AI/ML song song]
    
    subgraph Step3_Detail [Step 3: Động cơ AI/ML Phân tích Đa tầng]
        Step3 --> Step3A[Step 3A: OCR Banner Engine]
        Step3A --> S3A_1[Lọc ảnh ad-banner kích thước > 80x30]
        S3A_1 --> S3A_2[EasyOCR nhận dạng chữ tiếng Việt/Anh]
        S3A_2 --> S3A_3[3-Tier Cascade Matching]
        S3A_3 --> S3A_3_1[Tier 1: Khớp từ khóa chuẩn hóa Exact]
        S3A_3 --> S3A_3_2[Tier 2: Khớp mờ Fuzzy RapidFuzz]
        S3A_3 --> S3A_3_3[Tier 3: Cosine Semantic Embedding]
        
        Step3 --> Step3B[Step 3B: NLP Content Model]
        Step3B --> S3B_1[Text Segmenter với Overlap 256 từ]
        S3B_1 --> S3B_2[Multi-task PhoBERT Classifier]
        S3B_2 --> S3B_3[Task 1: An toàn vs Độc hại]
        S3B_2 --> S3B_4[Task 2: Loại website]
        S3B_3 & S3B_4 --> S3B_5[Aggregator: Max Pooling & Voting]
    end

    Step3A & Step3B --> Step4[Step 4: Gemini AI Synthesis & Verdict Reporting]
    
    subgraph Step4_Detail [Step 4: LLM Tổng hợp & Báo cáo]
        Step4 --> S4_1[Reducer: Trích xuất slim payload giảm 60-90% token]
        S4_1 --> S4_2[Gemini 3.5 Flash API Evaluator]
        S4_2 --> S4_3[Đối chiếu Khung 4 Lớp VNNIC: L1: Pháp lý, L2: Hạ tầng, L3: Doanh thu, L4: Nội dung]
        S4_3 --> S4_4[Phán quyết cuối cùng: VI_PHAM | NGHI_NGO | AN_TOAN]
        S4_4 --> S4_5[Đóng gói Hồ sơ Bằng chứng Pháp lý JSON / PDF]
    end
    
    Step4_Detail --> Output[Kết quả & Báo cáo]
```

---

## 2. Chi tiết Từng Bước Xử lý trong Pipeline

### Step 0: Whitelist Processing & Domain Model Pre-screening
Bước này đóng vai trò là chốt chặn đầu tiên giúp lọc nhanh các tên miền đáng tin cậy và phân loại sơ bộ các tên miền nguy hiểm.
1. **Tra cứu Whitelist VNNIC**:
   - URL đầu vào được chuẩn hóa (loại bỏ `http://`, `https://`, `www.`, các ký tự thừa).
   - Hệ thống so khớp tên miền này với Cơ sở dữ liệu Whitelist chính thức từ VNNIC (`danh_sach_domain_whitelist.csv`).
   - Nếu tên miền hoặc tên miền cha của nó khớp với whitelist, hệ thống đánh dấu flag `FLAG_TRUST_HIGH`.
2. **Domain Model (Hybrid Classifier)**:
   - Trích xuất **12 đặc trưng lexical & hosting** của tên miền:
     - `domain_length`: Độ dài chuỗi tên miền.
     - `entropy`: Chỉ số Shannon Entropy của chuỗi tên miền.
     - `percentage_digits`: Tỷ lệ ký tự số.
     - `special_chars`: Số lượng ký tự đặc biệt như `-`, `_`.
     - `is_cheap_tld`: Đánh dấu `1` nếu tên miền sử dụng các đuôi TLD rủi ro cao.
     - `passive_dns_len`: Số lượng bản ghi DNS loại A.
     - `unique_addresses`: Số lượng IP duy nhất trích xuất được.
     - `unique_hostnames`: Số lượng bản ghi DNS NS.
     - `asn_switch`: Cờ đánh dấu hosting đáng ngờ.
     - `ip_count`: Tổng số IP phân giải được.
     - `subdomain_depth`: Số cấp tên miền con.
     - `ttl_value`: Giá trị Time-to-Live của DNS.
   - Các đặc trưng số này được kết hợp với vector nhúng (embeddings) của chuỗi tên miền qua mô hình **PhoBERT Domain Model** để đưa ra phân loại sơ bộ xem tên miền có độc hại hay không (`FLAG_DOMAIN_PREDICT_MALICIOUS`).

### Step 1: Network Intelligence & Redirect Chain Tracking
Bước này tập trung vào việc thu thập thông tin "vân tay kỹ thuật" của hạ tầng mạng phục vụ cho việc tính toán điểm rủi ro.
1. **Phân tích WHOIS**:
   - Xác định ngày đăng ký tên miền và tính toán tuổi tên miền (`domain_age_days`).
   - Kiểm tra nhà đăng ký tên miền (`registrar`) và xếp hạng rủi ro (đặc biệt các nhà đăng ký rủi ro cao: Namecheap, Namesilo, Njalla).
   - Nhận diện trạng thái kích hoạt dịch vụ ẩn danh thông tin chủ sở hữu (`privacy_enabled`).
2. **Phân tích DNS**:
   - Thu thập đầy đủ các bản ghi A, NS, MX, TXT.
   - Nhận diện nhà cung cấp dịch vụ CDN (ví dụ Cloudflare, Akamai).
3. **Redirect Chain Tracking (Bám vết nhảy tên miền)**:
   - Theo dõi chuỗi chuyển hướng HTTP để bắt quả tang hành vi "nhảy tên miền" (domain hopping). Nếu phát hiện tên miền đích thay đổi so với tên miền ban đầu, hệ thống sẽ tự động cập nhật và chuyển hướng các phân tích của các bước sau sang tên miền mới này.
4. **Nhận diện Hạ tầng Hosting**:
   - Phân biệt giữa các **Cloud Provider chính thống** (AWS, GCP, Azure, Cloudflare) và các **Hosting chống gỡ bỏ/đáng ngờ** (OVH, Hetzner, DigitalOcean, Vultr, Hostinger, Contabo).
5. **Tính toán điểm số (Risk & Legitimacy Score)**:
   - **Risk Score (Điểm Rủi ro - Max 100)**:
     - Tuổi domain < 180 ngày: `+20`
     - Ẩn danh WHOIS: `+10`
     - Sử dụng Cloudflare: `+5`
     - Không cấu hình MX (không có mail doanh nghiệp): `+10`
     - Đuôi TLD rủi ro cao (ví dụ: `.xyz`, `.top`, `.cc`, `.to`): `+20`
     - Đuôi TLD rủi ro trung bình (ví dụ: `.tv`, `.live`, `.vip`, `.fun`): `+10`
     - Phát hiện nhảy tên miền (Domain Hopping): `+25`
     - Hosting nằm trong danh sách đáng ngờ: `+10`
   - **Legitimacy Score (Điểm Tin cậy - Max 100)**:
     - TLD chính thống Việt Nam/quốc tế (`.vn`, `.gov`, `.edu`, `.org`): `+15`
     - Có cấu hình mail doanh nghiệp: `+20`
     - Có mã xác minh Google Verification trong TXT record: `+10`
     - Đã cấu hình SPF: `+10`
     - Hosting chạy trên Cloud lớn (AWS, Azure, GCP): `+15`
     - Sử dụng DNS doanh nghiệp lớn: `+10`
     - Tuổi domain > 365 ngày: `+10` (hoặc > 730 ngày: `+20`)

### Step 2: Deep Browser Evidence Collection (Playwright)
Sử dụng công nghệ mô phỏng trình duyệt để thu thập các bằng chứng trực quan và hành vi động của trang web lậu.
1. **Playwright Stealth Browser**:
   - Sử dụng một trình duyệt Chromium không đầu kết hợp với thư viện `playwright_stealth` để vượt qua các lớp kiểm tra bot và thử thách JavaScript của Cloudflare.
2. **Cào dữ liệu chuyên sâu (Watch Pages Crawling)**:
   - Tự động tìm kiếm các liên kết xem phim/xem truyện chi tiết từ trang chủ bằng các Regex Pattern đặc trưng (ví dụ: `/tap-`, `/episode/`, `/watch/`, `/xem-phim/`).
3. **Đánh chặn Lưu lượng mạng (Network Request Interception)**:
   - Lắng nghe và chặn bắt các yêu cầu tải luồng video trực tuyến có đuôi `.m3u8`, `.mp4`, `.ts`, `.mpd`.
   - Trích xuất nguồn của các trình phát video nhúng trong thẻ iframe (như pstream, gdrive, ok.ru, fembed, doodstream...).
4. **Tự động chặn Pop-up & Ad Tabs**:
   - Phát hiện và tự động đóng các cửa sổ quảng cáo/tab mới tự mở khi click vào trang để tránh bị kẹt luồng cào dữ liệu.
5. **Footer Pháp lý**:
   - Phân tích văn bản khu vực chân trang (footer) để tìm kiếm các từ khóa pháp lý: Mã số thuế (MST), Giấy phép thiết lập mạng xã hội/trang thông tin điện tử, liên hệ DMCA, các kênh liên hệ mờ ám (chỉ có Telegram/Skype/Gmail rác).
6. **Chụp ảnh giao diện**:
   - Tự động chụp màn hình toàn bộ trang chủ và trang xem chi tiết làm bằng chứng lưu trữ dạng hình ảnh.

### Step 3: Động cơ Phân tích Đa tầng bằng AI/ML
Hệ thống kích hoạt đồng thời hai nhánh phân tích độc lập để bóc tách triệt để mô hình tài trợ và nội dung trang web:

#### Nhánh 3A: OCR Banner Engine (Phát hiện Tài trợ Đen)
Trang web vi phạm bản quyền hầu hết được tài trợ bởi quảng cáo cờ bạc, cá độ. Hệ thống sử dụng Computer Vision để phân tích điều này:
- **Lọc Banner**: Tách các tài nguyên ảnh quảng cáo dựa trên kích thước tối thiểu (rộng > 80px, cao > 30px) và loại trừ các ảnh poster/thumbnail phim nhờ các keyword về class/URL.
- **EasyOCR**: Trích xuất toàn bộ văn bản (tiếng Anh và tiếng Việt) trên các banner quảng cáo này.
- **Kiến trúc Cascade 3 Tầng (Fail-Fast)**:
  - *Tầng 1 - Khớp từ khóa Chuẩn hóa (Exact Match)*: Chuyển đổi text sang dạng viết thường, bỏ dấu tiếng Việt, loại bỏ emoji, sau đó so khớp chính xác với bộ từ khóa cá cược, cờ bạc.
  - *Tầng 2 - Khớp mờ (Fuzzy Match)*: Sử dụng `rapidfuzz` để so khớp mờ với ngưỡng similarity 75%. Tầng này giúp bắt các từ khóa bị lỗi nhận diện OCR (typo) hoặc cố tình viết chệch chữ.
  - *Tầng 3 - So khớp ngữ nghĩa (Semantic Embedding)*: Sử dụng mô hình `paraphrase-multilingual-MiniLM-L12-v2` chuyển đổi text sang không gian vector để tính độ tương đồng Cosine với ngân hàng cụm từ hạt giống (`GAMBLING_SEED_PHRASES`). Cách này giúp phát hiện các cách diễn đạt né từ khóa nhưng cùng nghĩa (ví dụ: *"hỗ trợ tài chính khi chơi"* $\approx$ *"cho vay đánh bạc"*).

#### Nhánh 3B: NLP Content Model (Phân loại Nội dung)
Phân tích trực tiếp nội dung văn bản cào được từ DOM để khẳng định bản chất trang web.
- **Text Segmenter with Overlap**: 
  - DOM text thường rất dài, hệ thống cắt nhỏ văn bản thành các phân đoạn (segments) tối đa 256 từ.
  - Từ phân đoạn thứ 2 trở đi, hệ thống sẽ thực hiện lùi lại 30-40 từ (overlap) và dò ngược lại để tìm các điểm ngắt câu tự nhiên (dấu chấm, dấu hỏi, dấu xuống dòng) nhằm đảm bảo ý nghĩa trọn vẹn cho mô hình NLP phân tích.
- **Multi-task PhoBERT Inference**:
  - Mỗi phân đoạn được chạy song song qua mô hình PhoBERT tinh chỉnh cho 2 nhiệm vụ:
    - *Task 1 (Binary)*: Phân loại nội dung là **An toàn (0)** hay **Độc hại (1)**.
    - *Task 2 (Multi-class)*: Phân loại danh mục cụ thể của trang web (Cờ bạc, 18+, Vay, Tiền ảo, E-commerce, MXH, Game, Báo chí...).
- **Max Pooling & Voting Aggregator**:
  - Tổng hợp kết quả từ tất cả các phân đoạn:
    - *Label*: Sử dụng Max Pooling (chỉ cần 1 phân đoạn bị gắn nhãn Độc hại $\rightarrow$ Toàn bộ trang web bị coi là Độc hại).
    - *Website Category*: Sử dụng cơ chế bỏ phiếu (Voting-based) trên kết quả của các phân đoạn để đưa ra danh mục trang web cuối cùng (tự động loại bỏ nhãn "Chưa xác định" nếu có các nhãn cụ thể khác chiếm ưu thế).

### Step 4: Gemini AI Synthesis & Verdict Reporting
Đây là bước cuối cùng, sử dụng trí tuệ nhân tạo để tổng hợp toàn bộ bằng chứng kỹ thuật rải rác từ Step 0 đến Step 3 thành một phán quyết chuẩn hóa.
1. **Reducer (Slim Payload)**:
   - Các dữ liệu thô cồng kềnh (toàn bộ DOM text, danh sách ảnh banner, danh sách DNS thô...) được cắt giảm từ 60% đến 90%.
   - Chỉ giữ lại khoảng **25 trường thông tin cốt lõi** (ví dụ: tuổi domain, các banner bị cờ đỏ kèm từ khóa match, kết quả phân loại NLP, các cờ kiểm tra pháp lý ở footer, các tín hiệu tin cậy...) để gửi tới Gemini API nhằm tối ưu hóa chi phí token và tốc độ phản hồi.
2. **Khung Đối chiếu 4 Lớp của VNNIC**:
   Gemini API nhận payload rút gọn và tiến hành đối chiếu với khung pháp lý 4 lớp:
   - **Lớp 1 — Định danh & Pháp lý**: Kiểm tra việc ẩn danh thông tin WHOIS, sự hiện diện của MST, giấy phép ICP/MXH, hoặc các thông tin liên hệ ẩn danh (Telegram/Skype/Gmail rác).
   - **Lớp 2 — Hạ tầng kỹ thuật**: Đánh giá các đuôi TLD lạ/rủi ro cao, hành vi nhảy tên miền liên tục, sử dụng Cloudflare miễn phí ẩn IP gốc, máy chủ đặt tại các host chống gỡ bỏ (OVH, Hetzner...).
   - **Lớp 3 — Mô hình doanh thu**: Phát hiện sự hiện diện của banner quảng cáo nhà cái, game bài cờ bạc (W88, Kubet, Fun88...), các hình thức thanh toán thẻ cào/crypto.
   - **Lớp 4 — Tính chất nội dung**: Nhận diện nội dung vi phạm bản quyền trực tiếp (phim lậu không có DRM, stream luồng bóng đá trực tiếp thu trộm đè logo, server game crack...).
3. **Quy tắc Phán quyết (Verdict)**:
   - `VI_PHAM`: Có bằng chứng rõ ràng ở Lớp 3 hoặc Lớp 4 (nội dung hoặc quảng cáo cá cược trực tiếp).
   - `NGHI_NGO`: Chỉ có các dấu hiệu đáng ngờ ở Lớp 1 & Lớp 2 (hạ tầng đáng ngờ, ẩn danh) nhưng chưa có nội dung vi phạm cụ thể.
   - `AN_TOAN`: Không phát hiện bất cứ dấu hiệu vi phạm nào ở cả 4 lớp.
4. **Báo cáo chuẩn hóa**:
   - Xuất dữ liệu ra file JSON báo cáo cuối cùng bao gồm phán quyết, độ tự tin (confidence score), các tín hiệu vi phạm chính (key signals) và hành động khuyến nghị pháp lý.

---

## 3. Cơ chế Lưu trữ Logs và Quản lý Cache

Để nâng cao hiệu năng và tránh quét trùng lặp gây hao tốn tài nguyên (đặc biệt là Playwright và API Call), hệ thống tích hợp hai cơ chế hoạt động:

1. **Chế độ CACHE MODE (Tối ưu tốc độ < 1 giây)**:
   - Mỗi lần quét hoàn tất, tất cả dữ liệu trung gian và báo cáo cuối cùng đều được lưu vào thư mục `logs/v1.0.4.1/<tên_miền_chuẩn_hóa>/`.
   - Cấu trúc các file log lưu trữ:
     - `*_step1_*.json`: Chứa dữ liệu thông tin mạng thu thập được.
     - `*_step2_*.json`: Chứa kết quả cào trình duyệt, DOM text, danh sách ảnh banner, iframe.
     - `*_final_*.json`: Kết hợp đầy đủ dữ liệu từ Step 0 đến Step 3.
     - `*_report_*.json`: Báo cáo kết luận cuối cùng (được Gemini tổng hợp).
   - Khi nhận yêu cầu quét mới, hệ thống tự động kiểm tra thư mục logs. Nếu kết quả đã tồn tại, hệ thống lập tức tải lên UI trong nháy mắt.

2. **Chế độ LIVE MODE (Thời gian thực)**:
   - Nếu domain chưa từng được phân tích (hoặc yêu cầu quét lại), hệ thống sẽ khởi tạo một luồng xử lý riêng biệt trong nền (`Pipeline Thread`).
   - Cập nhật tiến độ xử lý từng bước theo phần trăm đóng góp (`weight`):
     - **Step 0**: 10%
     - **Step 1**: 15%
     - **Step 2**: 35%
     - **Step 3A**: 20%
     - **Step 3B**: 10%
     - **Step 4**: 10%
   - Trạng thái tiến trình được phản hồi liên tục về giao diện người dùng theo thời gian thực (real-time progress bar & log stream).
