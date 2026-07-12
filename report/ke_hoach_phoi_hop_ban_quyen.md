# KẾ HOẠCH PHỐI HỢP GIÁM SÁT VI PHẠM BẢN QUYỀN SỐ — THÁNG 7-8/2026

Báo cáo này trình bày kế hoạch phối hợp giữa **VNNIC** và **Nhóm Nghiên cứu** nhằm kế thừa, phát triển hệ thống trí tuệ nhân tạo và thiết lập các bộ lọc bổ trợ phục vụ công tác tự động phát hiện, giám sát các website **có dấu hiệu vi phạm bản quyền** thuộc các lĩnh vực đặc thù và các hành vi vi phạm liên quan trên không gian mạng Việt Nam.

---

## PHẦN I: KẾ THỪA VÀ FINE-TUNE MÔ HÌNH NỘI DUNG (CONTENT MODEL) THEO 3 LĨNH VỰC VNNIC

Thay vì tổ chức gán nhãn dữ liệu quy mô lớn từ đầu, dự án của chúng ta thực hiện **kế thừa hoàn toàn mô hình nội dung PhoBERT** đã được huấn luyện từ đề tài trước để phân tích cấu trúc văn bản DOM (*DOM Text*). Định hướng nghiên cứu chính trong giai đoạn này là thực hiện **fine-tune mô hình** để phân loại và nhận diện các dấu hiệu vi phạm tập trung vào **3 lĩnh vực bản quyền đặc thù** do VNNIC cung cấp:

### 1. Chi tiết tiêu chí 3 lĩnh vực bản quyền đặc thù (Theo danh mục VNNIC)
Dựa trên tài liệu hướng dẫn và danh mục tiêu chí của VNNIC, mô hình nội dung sẽ được fine-tune để phát hiện các tín hiệu thuộc 3 nhóm chính:

#### a. Lĩnh vực đặc thù: Phim ảnh
*   **Có dấu hiệu vi phạm**:
    *   Cung cấp các bản quay lén rạp chiếu phim (*Bản CAM*), bản dịch tự phát (*Vietsub tự dịch*) cho các bộ phim đang chiếu rạp hoặc phim độc quyền chưa được phát hành thương mại.
    *   Hệ thống máy chủ lưu trữ trực tiếp file video lậu (`.mp4`, `.m3u8`...) không có cơ chế bảo vệ bản quyền số DRM, dễ dàng bị thu giữ link stream qua F12 hoặc các công cụ bắt link.
*   **Không có dấu hiệu vi phạm (An toàn)**:
    *   Trang cung cấp dịch vụ xem phim chính thống của các đài truyền hình hoặc đơn vị được ủy quyền, sử dụng hệ thống bảo vệ bản quyền số DRM nghiêm ngặt, chặn thu giữ token và luồng phát được mã hóa.

#### b. Lĩnh vực đặc thù: Bóng đá / Thể thao
*   **Có dấu hiệu vi phạm**:
    *   Thu trộm trực tiếp tín hiệu phát sóng sạch từ các đơn vị sở hữu bản quyền truyền hình tại Việt Nam (như K+, TV360, FPT Play) và phát sóng lại trái phép.
    *   Cố tình đè đè logo của các trang web lậu khác (ví dụ: `Xoilac`, `Thapcam`, `90phut`) lên góc màn hình; có bình luận viên tự phát sử dụng từ ngữ không chuẩn mực, tục tĩu hoặc lồng ghép quảng bá cá độ bóng đá.
*   **Không có dấu hiệu vi phạm (An toàn)**:
    *   Trang phát sóng của các đơn vị sở hữu bản quyền chính thức, tín hiệu phát sóng nguyên bản có DRM mã hóa, đội ngũ bình luận viên chuyên nghiệp và sử dụng hạ tầng CDN phân phối chính thống.

#### c. Lĩnh vực đặc thù: Game
*   **Có dấu hiệu vi phạm**:
    *   Chia sẻ liên kết tải trực tiếp các bản bẻ khóa game (*Game crack*), bản chỉnh sửa (*Mod game*), file cài đặt ứng dụng Android ngoài store (*file APK*) dễ chứa mã độc.
    *   Quảng bá hoặc cung cấp đường dẫn truy cập vào các máy chủ game lậu tự phát (*Private Server*) không có bản quyền từ nhà phát hành gốc; viết tài liệu hướng dẫn người dùng tắt phần mềm diệt virus hoặc Windows Defender để cài đặt game lậu.
*   **Không có dấu hiệu vi phạm (An toàn)**:
    *   Giới thiệu game bản quyền hoặc điều hướng người dùng mua game chính thống qua các chợ ứng dụng (Google Play, App Store, Steam, Epic Games); máy chủ vận hành chính thức của nhà phát hành được cấp phép kịch bản game.

---

### 2. Định hướng và quy trình tinh chỉnh mô hình (Fine-tune)
*   **Mục tiêu fine-tune (nếu được)**: Điều chỉnh cấu trúc đầu ra của mô hình nội dung PhoBERT kế thừa từ đề tài cũ. Chuyển đổi từ phân loại các thể loại nội dung chung (Báo chí, MXH, 18+...) sang dự đoán trực tiếp tỷ lệ xác suất **có dấu hiệu vi phạm bản quyền** thuộc 3 nhóm: Phim ảnh, Bóng đá, và Game.
*   **Cơ chế hậu kiểm dữ liệu fine-tune**: Để phục vụ quá trình tinh chỉnh mô hình trên tập mẫu nhỏ, *nếu đủ thời gian, nên có quy trình review lại các nhãn đã được gán* bởi chuyên viên nghiệp vụ để bảo đảm dữ liệu đưa vào huấn luyện đạt độ tin cậy tuyệt đối, tránh sai lệch nhãn.

---

## PHẦN II: KẾ THỪA MÔ HÌNH TÊN MIỀN (DOMAIN MODEL) PRE-SCREENING

Hệ thống **kế thừa hoàn toàn mô hình phân loại tên miền** (*Domain Model*) để thực hiện nhiệm vụ quét sơ bộ (*pre-screening*) tại Step 0 của quy trình giám sát. Bước này giúp nhận diện nhanh các tên miền đáng ngờ ngay cả khi trang web đang ở trạng thái không hoạt động hoặc bị chặn truy cập.

### 1. Vận hành và các đặc trưng kỹ thuật kế thừa
Mô hình hoạt động hoàn toàn ở mức phân tích cấu trúc cú pháp tên miền và các tín hiệu mạng DNS/Hosting, trích xuất tự động 12 đặc trưng kỹ thuật làm đầu vào cho bộ phân loại (như được triển khai trong [step0.py](file:///e:/Hoc_Tap/copyright%20detection%20project/step0.py#L170-L251)):

#### a. Nhóm đặc trưng Cú pháp (Lexical Features)
1.  **length**: Độ dài ký tự của tên miền.
2.  **entropy**: Shannon entropy đo mức độ ngẫu nhiên của các ký tự cấu thành tên miền (phát hiện tên miền rác tạo bằng thuật toán DGA).
3.  **percent_num**: Tỷ lệ chữ số xuất hiện trong tên miền (ví dụ: `phimmoiz2`, `xoilac7`).
4.  **num_special**: Số lượng ký tự đặc biệt (như dấu `-` và `_`) trong tên miền.
5.  **is_cheap_tld**: Xác định tên miền có đăng ký TLD giá rẻ hoặc rủi ro cao hay không (như `.to`, `.cc`, `.xyz`, `.top`, `.club`).
6.  **subdomain_depth**: Số cấp subdomain xuất hiện trước tên miền chính (ví dụ: `abc.xyz.com.vn` có depth là 4).

#### b. Nhóm đặc trưng Mạng và DNS (Hosting / DNS Features)
7.  **hostname_length**: Độ dài ký tự của hostname đầy đủ.
8.  **passive_dns_len**: Số lượng bản ghi A (IP phân giải) thu thập được từ DNS.
9.  **unique_addresses_count**: Số IP duy nhất mà tên miền từng trỏ tới trong lịch sử.
10. **unique_hostnames_count**: Số Name Server (NS) liên kết với tên miền.
11. **asn_switch_count**: Số lần dịch chuyển tên miền giữa các số hiệu mạng tự trị (ASN) khác nhau trong lịch sử.
12. **ip_address_count**: Tổng số IP được ghi nhận trỏ tới từ tên miền.
13. **ttl_value**: Thời gian tồn tại bản ghi trong cache DNS (Time-To-Live).

### 2. Hạn chế & Hướng cải thiện
*   *Hạn chế*: Mô hình tên miền chỉ đánh giá hạ tầng mạng nên không thể biết nội dung thực tế trên trang web là gì, dễ dẫn đến cảnh báo nhầm đối với các website hợp pháp sử dụng CDN ẩn danh (như Cloudflare proxy).
*   *Hướng cải thiện (nếu được)*: Tích hợp thêm bộ lọc nhà đăng ký tên miền đáng tin cậy để làm giàu thông tin đầu vào cho mô hình pre-screening.

---

## PHẦN III: KIẾN TRÚC BỘ LỌC BỔ TRỢ VÀ QUY TRÌNH GIÁM SÁT 4 GIAI ĐOẠN

Nhằm khắc phục các hạn chế nội tại của mô hình AI và giảm thiểu tối đa sai sót, hệ thống được vận hành theo kiến trúc kết hợp giữa **Mô hình Trí tuệ nhân tạo**, **Các bộ lọc quy tắc nghiệp vụ** và **Thẩm định viên (Con người)**.

### 1. Vai trò của mô hình AI và các bộ lọc bổ trợ
*   **Mô hình AI**: Sàng lọc diện rộng, nhận diện nhanh các phân đoạn **có dấu hiệu vi phạm** dựa trên dữ liệu đã huấn luyện. AI chỉ đóng vai trò cung cấp tín hiệu cảnh báo có trọng số, không đưa ra phán quyết pháp lý tuyệt đối.
*   **Bộ lọc bổ trợ**: Hoạt động dựa trên các luật nghiệp vụ cứng (*Rule-based*) để giảm tỷ lệ bỏ sót (FN) và giảm bắt dư (FP) *(nếu được)*, đồng thời lưu trữ hình ảnh banner quảng cáo cờ bạc hoặc link stream lậu để làm bằng chứng kỹ thuật phục vụ thẩm định.

### 2. Quy trình giám sát và phát hiện 4 giai đoạn
Hệ thống giám sát vận hành qua một đường ống xử lý (*Pipeline*) gồm:
1.  **Giai đoạn 1 (Tiền kiểm)**: Lọc trùng whitelist và chạy bộ lọc có khả năng giả mạo tên miền thương hiệu.
2.  **Giai đoạn 2 (Đánh giá AI)**: Chạy song song Domain Model (Step 0), Content Model fine-tuned (Step 3) và OCR Engine phát hiện banner quảng cáo cá cược (lớp doanh thu).
3.  **Giai đoạn 3 (Hậu kiểm bằng bộ lọc)**: Chạy song song các bộ lọc nghiệp vụ (bộ lọc từ khóa vi phạm bản quyền, kiểm tra danh sách báo chí/game cấp phép, kiểm tra redirect chéo tên miền).
4.  **Giai đoạn 4 (Hậu kiểm con người - Human-in-the-loop)**: Đối với các trường hợp phức tạp (như trang thông tin chính trị, trang có nghiệp vụ đặc thù), chuyên viên nghiệp vụ của VNNIC sẽ kiểm tra bằng chứng kỹ thuật được hệ thống ghi nhận để **đưa ra kết luận cuối cùng**.

---

### 3. Phân loại và đánh giá độ ưu tiên của các bộ lọc
Các bộ lọc hỗ trợ được phân chia mức độ ưu tiên theo đúng nghiệp vụ thực tế và góp ý của thầy:

#### a. Các bộ lọc phía Đối tác Nghiên cứu phát triển
*   **Bộ lọc từ khóa bản quyền** *(Rất cần thiết)*:
    *   *Mô tả*: Quét trực tiếp nội dung văn bản DOM để tìm các từ khóa đặc trưng chỉ xuất hiện ở trang lậu (ví dụ: `full vietsub`, `bản cam quay lén`, `xem phim nhanh`, `trực tiếp bóng đá xoilac`, `link sopcast`, `crack game`, `full crack`, `private server`).
*   **Bộ lọc có khả năng giả mạo tên miền** *(Rất cần thiết)*:
    *   *Mô tả*: Sử dụng thuật toán đo khoảng cách Levenshtein để phát hiện các tên miền cố tình viết sai chính tả, thêm bớt ký tự nhằm mạo danh các cơ quan, tổ chức hoặc thương hiệu lớn (ví dụ: `vtvgo.vn` bị mạo danh thành `vtvg0.vn` hoặc `vtvgo.xyz`).
    *   *Hạn chế hiện tại*: Bộ lọc này hiện tại **chỉ giới hạn ở mức phân tích cấu trúc tên miền cú pháp**, chưa hỗ trợ so khớp hay phân tích hành vi giả mạo nội dung giao diện website.
    *   *Hướng phát triển*: Tích hợp thêm module **đối sánh nội dung chi tiết giữa hai trang web** (trang gốc và trang nghi ngờ giả mạo) để phát hiện hành vi sao chép bố cục, hình ảnh, văn bản nhằm khẳng định mức độ giả mạo nội dung.
*   **Hậu kiểm bằng AI Hybrid Model** *(Ít phổ biến)*:
    *   *Mô tả*: Sử dụng mô hình lai kết hợp học sâu và các luật nghiệp vụ cứng để tái đánh giá các tên miền có dấu hiệu vi phạm cao.

#### b. Các bộ lọc do VNNIC phát triển và tích hợp
*   **Bộ lọc Whitelist / Blacklist** *(Rất cần thiết)*:
    *   *Mô tả*: Quản lý danh sách các tên miền sạch được bảo vệ (cơ quan chính phủ, báo chí lớn) để loại trừ ngay lập tức; đồng thời quản lý danh sách đen các tên miền đã xác định vi phạm để xử lý nhanh.
*   **Bộ lọc Báo chí cấp phép** *(Rất cần thiết)*:
    *   *Mô tả*: Đối chiếu tự động với cơ sở dữ liệu các cơ quan báo chí, trang tin tổng hợp đã được cấp giấy phép hoạt động chính thức của Bộ Thông tin & Truyền thông. Nếu một website tự xưng là trang báo chí/tin tức điện tử nhưng không nằm trong danh sách này, hệ thống sẽ tự động hạ mức độ tin cậy và gắn nhãn cảnh báo.
*   **Bộ lọc Game cấp phép** *(Rất cần thiết)*:
    *   *Mô tả*: Đối chiếu các tên miền cung cấp dịch vụ trò chơi trực tuyến với danh sách các game đã được cấp quyết định phê duyệt nội dung, kịch bản G1, G2, G3, G4 tại Việt Nam. Các website cung cấp link tải hoặc dịch vụ game không phép sẽ bị đưa vào danh sách theo dõi đặc biệt.
*   **Bộ lọc chuyển hướng đến trang khác (Redirect)** *(Cần thiết)*:
    *   *Mô tả*: Giám sát hành vi chuyển hướng tự động (qua mã HTTP redirect hoặc mã Javascript ẩn) từ tên miền ban đầu sang tên miền đích khác.
*   **Bộ lọc Sàn giao dịch được cấp phép** *(Cần thiết)*:
    *   *Mô tả*: Kiểm tra, đối chiếu thông tin sàn giao dịch chứng khoán, sàn giao dịch tài chính với danh sách được Ủy ban Chứng khoán Nhà nước cấp phép hoạt động.
*   **Bộ lọc Nhà đăng ký tin cậy** *(Ít phổ biến)*:
    *   *Mô tả*: Đánh giá mức độ rủi ro dựa trên nhà đăng ký tên miền (*Registrar*).

---

### 4. Thiết kế giao tiếp và Đánh giá hiệu quả
*   **Module hóa độc lập**: Mỗi bộ lọc được thiết kế thành một module dịch vụ riêng, hỗ trợ gọi API trực tiếp để kiểm tra nhanh.
*   **Đường ống tổng hợp (Pipeline Endpoint)**: Thiết lập một endpoint chung duy nhất nhận đầu vào là URL và tự động chạy toàn bộ pipeline từ Giai đoạn 1 đến Giai đoạn 3, trả về kết quả tổng hợp.
*   **Đánh giá hiệu quả thực tế**: Sử dụng phương pháp *Ablation Study* so sánh Precision/Recall/F1 giữa các cấu hình, phân tích tỷ lệ giảm sai số (FN, FP) *(nếu được)* và đối sánh chéo với danh sách website vi phạm thực tế từ chuyên viên VNNIC làm Ground Truth.
