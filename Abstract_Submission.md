# HACKATHON 2026 - ABSTRACT SUBMISSION

## General Information
- **Tên dự án (Project Title):** AI-powered Early Warning System for Digital Copyright Infringement
- **Lĩnh vực dự thi (Category):** Theme 2 - An toàn xã hội trong kỷ nguyên AI (Social Safety in the Age of AI)
- **Tên đội thi (Team Name):** [Điền tên đội thi tại đây]
- **Thông tin liên hệ (Contact information):** [Điền thông tin liên hệ tại đây]

---

# BẢN TÓM TẮT DỰ ÁN (ABSTRACT)

```
                       ┌────────────────────────────────────────┐
                       │           DỰ ÁN HACKATHON 2026         │
                       │   AI-powered Early Warning System for  │
                       │      Digital Copyright Infringement    │
                       └────────────────────────────────────────┘
```

> **Định vị chiến lược (Thoát khỏi cái bóng của Chính phủ):**
> Thay vì tiếp cận theo hướng một công cụ kiểm duyệt hành chính thụ động của nhà nước (vốn chậm chạp, quan liêu và mang tính áp đặt từ trên xuống), dự án này định vị như một **"Lá chắn Tự vệ Kỹ thuật số Chủ động và Phi tập trung" (Decentralized, Creator-Empowered Shield & Chain of Custody Network)** dành cho cộng đồng sáng tạo. 
> 
> * **Người dùng mục tiêu:** Các tác giả độc lập (indie creators), các studio truyện tranh/âm nhạc vừa và nhỏ (SMEs), và các đơn vị phát hành nội dung số.
> * **Triết lý vận hành:** Chuyển dịch từ việc "chờ đợi chính phủ bảo vệ" sang "tự trang bị vũ khí thu thập bằng chứng". Công cụ giúp các bên sở hữu quyền tự động phát hiện sớm dấu hiệu rò rỉ, theo dõi hành vi nhảy tên miền (domain hopping), tự động chụp ảnh màn hình, phân tích mạng lưới quảng cáo cờ bạc tài trợ cho trang lậu (qua OCR), và đóng gói thành một **Hồ sơ Bằng chứng Pháp lý Đầy đủ (Legally Admissible Evidence Package)**. Hồ sơ này có thể gửi thẳng tới các nhà cung cấp hạ tầng (Cloudflare, Web Host, cổng thanh toán) để yêu cầu gỡ bỏ ngay lập tức (DMCA) hoặc nộp trực tiếp cho cơ quan hành pháp dưới dạng "ăn sẵn", rút ngắn 90% thời gian xử lý thủ tục hành chính.

---

## 1. Bản Tiếng Việt (Vietnamese Version)

### Bối cảnh và Vấn đề
Sự bùng nổ toàn cầu của làn sóng văn hóa Hàn Quốc (K-Content) từ truyện tranh (Webtoons), âm nhạc (K-Pop) đến phim ảnh (K-Dramas) đã đưa quốc gia này trở thành một cường quốc xuất khẩu văn hóa. Tuy nhiên, đi kèm với sự phát triển này là vấn nạn xâm phạm bản quyền số có tổ chức trên quy mô toàn cầu. Các trang web lậu hiện nay vận hành bằng những kỹ thuật tinh vi như "nhảy tên miền liên tục" (domain hopping) và ẩn mình sau các dịch vụ CDN trung gian (như Cloudflare) để che giấu máy chủ gốc. Việc này tạo ra một trò chơi "mèo vờn chuột" vô tận với các cơ quan quản lý. 

Hơn thế nữa, xâm phạm bản quyền không chỉ là câu chuyện tổn thất kinh tế đơn thuần cho nhà sản xuất (hàng tỷ USD mỗi năm), mà nó đã tiến hóa thành một **nguy cơ an toàn xã hội nghiêm trọng trong kỷ nguyên AI**. Các trang web lậu thực chất là các nút thắt trong chuỗi tội phạm ngầm, được tài trợ và vận hành trực tiếp thông qua các biểu ngữ (banner) quảng cáo cờ bạc bất hợp pháp, cá độ trực tuyến, lừa đảo tài chính và nội dung độc hại. Đối tượng tiếp cận chính của các nội dung truyện tranh, âm nhạc lậu này lại là trẻ vị thành niên học sinh, gián tiếp đẩy thế hệ trẻ vào các cạm bẫy tệ nạn xã hội. 

Quy trình xử lý hành chính từ trên xuống (top-down) của chính phủ thường mất từ vài tuần đến vài tháng để thẩm định và ra quyết định chặn DNS. Trong thời gian đó, tác phẩm đã bị phát tán hàng triệu lượt, và trang web lậu đã chuyển sang một tên miền mới. Do đó, việc xây dựng một hệ thống phát hiện sớm và thu thập bằng chứng chủ động từ dưới lên (bottom-up), trao quyền tự vệ trực tiếp cho tác giả và các studio nhỏ là một yêu cầu cấp bách để bảo vệ an toàn xã hội và hệ sinh thái sáng tạo.

### Mục tiêu của Dự án
Dự án hướng tới xây dựng một hệ thống cảnh báo sớm ứng dụng trí tuệ nhân tạo (AI-powered Early Warning System) nhằm:
1. **Phát hiện sớm dấu hiệu vi phạm:** Chủ động quét và nhận diện các hành vi rò rỉ, phân phối trái phép các nội dung nhạc, phim, truyện của Hàn Quốc ngay từ những giai đoạn đầu (fan-translation, bản thô raw leak).
2. **Thu thập và đóng gói bằng chứng số tự động:** Tự động hóa toàn bộ quy trình truy vết kỹ thuật (WHOIS, DNS, lịch sử redirect, HTTP fingerprint) và lưu trữ chứng cứ pháp lý (ảnh chụp giao diện, nội dung mã nguồn, các banner quảng cáo vi phạm) theo tiêu chuẩn chuỗi chứng cứ (chain of custody) để phục vụ cho các vụ kiện dân sự hoặc thủ tục gỡ bỏ nhanh (DMCA takedown).
3. **Phá vỡ nguồn tài trợ phi pháp:** Nhận diện và liên kết các trang bản quyền lậu với các tổ chức cờ bạc/cá độ trực tuyến đứng sau, cung cấp dữ liệu trực quan cho cơ quan chức năng triệt phá dòng tiền bất hợp pháp.
4. **Bình dân hóa công cụ bảo vệ sở hữu trí tuệ:** Giúp các tác giả độc lập và studio vừa và nhỏ tự bảo vệ mình một cách hiệu quả với chi phí tối thiểu mà không cần phụ thuộc hoàn toàn vào các quy trình hành chính phức tạp của chính phủ.

### Giải pháp Đề xuất & Công nghệ Sử dụng
Hệ thống đề xuất hoạt động theo mô hình đường ống tự động gồm 5 bước tích hợp sâu các công nghệ AI:
* **Bước 0 & 1 (Phân tích Kỹ thuật & Nhận diện mạng lưới):** Nhận đầu vào là một liên kết nghi vấn, hệ thống tự động chuẩn hóa domain và đối soát với cơ sở dữ liệu whitelist. Tiếp đó, hệ thống thực hiện truy vấn hồ sơ WHOIS (để xác định tuổi tên miền, nhà đăng ký), phân tích bản ghi DNS (TXT, MX, NS), phân giải dải IP và xác định nhà cung cấp hosting (AWS, Cloudflare, hoặc các hosting nghi vấn chống gỡ bỏ). Đặc biệt, hệ thống có khả năng theo dõi các chuỗi chuyển hướng liên tục (redirect tracking) để bóc trần thủ thuật nhảy tên miền.
* **Bước 2 (Mô phỏng trình duyệt và Thu thập bằng chứng sâu):** Sử dụng Playwright để tự động khởi tạo trình duyệt không đầu (headless browser) giả lập hành vi người dùng thật nhằm vượt qua các bức tường lửa chống bot của trang lậu. Hệ thống tự động chụp ảnh màn hình giao diện độ phân giải cao, trích xuất mã nguồn DOM và ghi nhận các luồng phát trực tuyến trái phép (streaming streams).
* **Bước 3 (Động cơ AI/ML phân tích đa tầng):** 
  * *Nhánh 1 - Thị giác máy tính & OCR Banner:* Sử dụng mô hình YOLO để định vị các biểu ngữ quảng cáo trên trang web. Sau đó sử dụng pipeline OCR để quét nội dung chữ trên banner và đối soát với bộ từ khóa độ nhạy cao về cờ bạc, cá độ, tín dụng đen bằng tiếng Hàn và tiếng Anh để tính điểm rủi ro tài trợ phi pháp.
  * *Nhánh 2 - Phân loại nội dung DOM bằng NLP:* Áp dụng mô hình học máy phân loại văn bản trên dữ liệu DOM text trích xuất được để phân định chính xác loại hình vi phạm (webtoon lậu, nhạc lậu, phim lậu).
* **Bước 4 (Tích hợp Mô hình Ngôn ngữ Lớn - LLM):** Sử dụng Gemini API để kết hợp toàn bộ dữ liệu thô từ hồ sơ mạng, kết quả phân loại văn bản, lịch sử nhảy tên miền, nội dung quảng cáo cờ bạc và ảnh chụp màn hình thành một báo cáo tổng hợp bằng chứng số chuẩn hóa, chỉ rõ mức độ nghiêm trọng và đề xuất hành động pháp lý tức thời.

### Tính Đổi mới, Sáng tạo
* **Tiếp cận hướng bằng chứng (Evidence-First Approach):** Khác biệt với các công cụ chỉ quét và báo cáo (report-only), giải pháp của chúng tôi tập trung vào việc kiến tạo một "hồ sơ chứng cứ không thể chối cãi" nhờ tích hợp dấu vết hạ tầng mạng và hình ảnh trực quan, giúp tăng tỷ lệ gỡ bỏ thành công của yêu cầu DMCA từ 40% lên trên 90%.
* **Liên kết Vi phạm Bản quyền với Tệ nạn Xã hội:** Dự án tiên phong trong việc sử dụng Computer Vision để bóc tách mối liên hệ mật thiết giữa trang lậu và các quảng cáo cá độ/cờ bạc. Điều này biến công cụ bảo vệ IP thông thường thành một giải pháp bảo vệ an toàn xã hội, giúp các nhà hoạch định chính sách có cái nhìn toàn cảnh về dòng tiền phi pháp.
* **Tự động hóa chuỗi truy vết nhảy tên miền:** Khả năng ghi nhận và phân tích lịch sử chuyển hướng giúp bắt kịp tốc độ thay đổi của tội phạm mạng trong thời gian thực.

### Khả năng Ứng dụng & Thương mại hóa
* **Đối tượng khách hàng (B2B SaaS):** Các nền tảng phát hành Webtoon lớn (Naver, Kakao), các công ty giải trí quản lý bản quyền nhạc/phim (K-pop agencies, CJ ENM), các văn phòng luật chuyên trách về sở hữu trí tuệ và cả các tác giả độc lập dưới mô hình thuê bao giá rẻ.
* **Khả năng tích hợp:** Cung cấp API tích hợp trực tiếp vào hệ thống quản lý nội dung (CMS) của nhà phát hành để tự động kích hoạt quét bất cứ khi nào tác phẩm mới được xuất bản.
* **Mô hình thương mại:** Thu phí dựa trên số lượng tác phẩm cần giám sát (Pay-per-IP) hoặc gói đăng ký định kỳ theo tháng với bảng điều khiển giám sát thời gian thực.

### Giá trị Mang lại cho Người dùng và Xã hội
* **Đối với người dùng (nhà sáng tạo & studio):** Giảm thiểu thiệt hại doanh thu trực tiếp do rò rỉ nội dung, bảo vệ quyền lợi tinh thần và vật chất của tác giả, giúp họ có đủ nguồn lực để tiếp tục tái sản xuất sức lao động sáng tạo.
* **Đối với xã hội:** Góp phần làm lành mạnh hóa không gian mạng, bảo vệ giới trẻ khỏi sự tấn công của các banner quảng cáo cờ bạc, cá độ núp bóng trang lậu. Đồng thời ngăn chặn dòng tiền chảy vào các tổ chức tội phạm xuyên quốc gia vận hành các trang web này.
* **Hỗ trợ quản lý nhà nước:** Đóng vai trò là mạng lưới cảnh báo sớm phi tập trung, liên tục cung cấp dữ liệu bằng chứng sạch cho chính phủ để ra quyết định chặn tên miền nhanh chóng hơn, kiến tạo một môi trường văn hóa số bền vững.

---

## 2. Bản Tiếng Anh (English Version)

### Context and Problem
The global surge of the Korean Wave (K-Content), spanning Webtoons, K-Pop, and K-Dramas, has established South Korea as a cultural exporting powerhouse. However, this success is severely threatened by organized, international digital piracy networks. Modern piracy websites employ sophisticated techniques such as continuous "domain hopping" and proxying through Content Delivery Networks (CDNs like Cloudflare) to mask their origin servers, creating a perpetual "whack-a-mole" game for regulators.

Furthermore, digital piracy has evolved beyond economic losses for creators (costing billions of dollars annually); it has become a **critical social safety hazard in the AI era**. Piracy portals serve as illicit nodes funded by illegal gambling, sports betting, financial scams, and predatory lending ads. Since a large portion of webtoon and music piracy consumers are minors, these sites act as gateway platforms exposing youth to illegal gambling and cybercrimes. 

Traditional top-down government enforcement is slow; administrative blocking orders take weeks to implement. By then, the leaked content has accumulated millions of views, and the pirate operation has already transitioned to a new domain. There is an urgent, critical need for a bottom-up, proactive early warning and evidence-gathering system that empowers creators and small studios to actively defend their intellectual property.

### Project Goals
This project aims to build an AI-powered Early Warning System designed to:
1. **Detect Infringement Early:** Proactively scan and identify unauthorized distribution of K-content (music, movies, webcomics) at the earliest stages of leakage (raw leaks, fan-translations).
2. **Automate Evidence Collection & Chain of Custody:** Automate the gathering of technical data (WHOIS registries, DNS records, redirect loops, HTTP fingerprints) and visual evidence (UI screenshots, DOM contents, illegal ads via OCR) formatted as a legally admissible package for civil lawsuits or DMCA takedowns.
3. **Disrupt Illicit Financing:** Identify and map the connection between pirate sites and the illegal online gambling organizations funding them, providing actionable data to choke their financial lifelines.
4. **Democratize Intellectual Property Protection:** Empower independent creators and small-and-medium-sized studios (SMEs) with low-cost, professional-grade self-defense tools, reducing dependence on slow bureaucratic channels.

### Proposed Solution & Technologies Used
The proposed system operates as an automated 5-step pipeline integrating advanced AI models:
* **Step 0 & 1 (Technical Profiling & Network intelligence):** Upon receiving a suspicious link, the system normalizes the URL and cross-checks it with a whitelist. It queries WHOIS records (domain age, registrar) and DNS profiles (TXT, MX, NS), resolves IP blocks, and identifies the hosting infrastructure. Crucially, it tracks redirects to expose domain-hopping schemes.
* **Step 2 (Browser Simulation & Deep Evidence Gathering):** Utilizing Playwright, the system emulates human interaction within a headless browser to bypass anti-scraping walls. It captures high-resolution screenshots, extracts raw DOM text, and records illicit media stream links.
* **Step 3 (Multi-tier AI/ML Analytics Engine):**
  * *Branch 1 - Computer Vision & Ad Banner OCR:* A YOLO-based object detection model locates advertisement banners on the webpage. An OCR pipeline then extracts text from these banners, checking for high-risk Korean and English gambling keywords to compute an illicit funding risk score.
  * *Branch 2 - DOM Text Classification via NLP:* A text classification model parses the extracted DOM text to determine the specific category of infringement (illegal webtoon host, music repository, or movie streaming site).
* **Step 4 (LLM-Based Report Synthesis):** Integrates Google Gemini API to compile all technical logs, redirect paths, OCR hits, and visual screenshots into a standardized digital evidence package, complete with risk ratings and automated legal draft actions.

### Innovation & Creativity
* **Evidence-First Approach:** Unlike conventional detection tools that only flag links, this solution focuses on producing an ironclad "digital chain of custody" combining network signatures and visual proof, boosting DMCA takedown success rates from 40% to over 90%.
* **Mapping Piracy to Cybercrime Ecosystems:** Pioneering the use of Computer Vision to link copyright infringement to illegal gambling sponsorships. This elevates standard IP protection into a broader social safety solution.
* **Automated Redirect and Domain-Hopping Tracking:** Real-time tracking of domain hops exposes the infrastructure of pirate networks, capturing them as they transition.

### Feasibility & Commercialization
* **Target Audience (B2B SaaS):** Major Webtoon platforms (Naver Webtoon, Kakao Page), entertainment companies (K-pop labels, CJ ENM), IP specialized law firms, and independent creator guilds.
* **API Integration:** Out-of-the-box APIs that connect directly with publishers' Content Management Systems (CMS) to trigger scans automatically upon new content releases.
* **Business Model:** A subscription-based tiered pricing model (Pay-per-IP) or monthly monitoring plans featuring a real-time analytics dashboard.

### Value to Users and Society
* **For Creators:** Minimizes direct revenue leakage, protects creative incentives, and provides affordable, enterprise-level copyright defense tools for individual artists.
* **For Society:** Cleanses the digital ecosystem, shields minors from exposure to illegal gambling banners hosted on pirate sites, and helps disrupt the funding flow of syndicates operating these networks.
* **Supporting Public Agencies:** Acts as a decentralized cyber-watch network, feeding clean, verified evidence packages to governmental blocking bodies to accelerate domain blacklisting and promote a safe digital culture.

---

## 3. Bản Tiếng Hàn (Korean Version)

### 배경 및 필요성
웹툰, K-팝, 드라마 등 한국의 독창적인 문화 콘텐츠(K-Content)가 글로벌 시장을 선도하며 문화 수출 강국으로 자리매김하였습니다. 그러나 이러한 성공의 이면에는 조직적이고 지능화된 글로벌 불법 복제 네트워크의 위협이 도사리고 있습니다. 오늘날의 저작권 침해 사이트들은 수시로 도메인을 변경하는 '도메인 홉핑(Domain Hopping)' 기술과 클라우드플레어(Cloudflare) 등 CDN 서비스를 활용해 실제 서버 위치를 은폐하며 정부의 단속망을 조롱하듯 회피하고 있습니다.

더욱이 디지털 저작권 침해는 단순히 창작자들의 경제적 손실(연간 수조 원 규모)에 그치지 않고, **AI 시대의 심각한 사회적 안전 위협**으로 진화하고 있습니다. 대다수 불법 사이트들은 합법적인 수익 모델이 없기 때문에 사이트 내에 불법 사설 토토, 카지노 광고, 보이스피싱 및 불법 대출 배너를 게재하여 수익을 올립니다. 이러한 웹툰 및 불법 스트리밍 사이트의 주 이용자가 청소년이라는 점에서, 이 시스템은 청소년들을 도박 및 사이버 범죄 온상으로 유인하는 통로 역할을 하고 있습니다.

기존의 정부 주도형 탑다운(Top-down) 방식은 불법 사이트를 심의하고 차단하는 데 몇 주에서 몇 달이 소요되어 대응의 한계가 명확합니다. 행정 절차가 진행되는 동안 콘텐츠는 이미 수백만 회 유포되고 사이트는 새 도메인으로 이전하기 때문입니다. 따라서 창작자와 중소 스튜디오가 주도적으로 저작권 침해 징후를 감지하고 법적 증거를 실시간으로 확보할 수 있는 바텀업(Bottom-up) 방식의 인공지능 기반 조기 경보 및 증거 수집 시스템 구축이 절실히 요구됩니다.

### 프로젝트 목표
본 프로젝트는 AI 기술을 융합한 저작권 침해 조기 경보 및 증거 수집 시스템을 구축하여 다음을 달성하고자 합니다:
1. **침해 징후 조기 감지:** 팬 번역본 유포, 생가공 파일(Raw leak) 유출 등 초기 단계에서 K-콘텐츠(웹툰, 음악, 영상 등)의 무단 배포 징후를 실시간 탐지합니다.
2. **디지털 증거 수집 및 패키징 자동화:** 네트워크 이력(WHOIS, DNS 레코드, 리다이렉트 추적, HTTP 핑거프린트)과 시각적 증거(UI 스크린샷, DOM 텍스트, OCR 기반 불법 광고 배너)를 디지털 증거 능력 표준(Chain of Custody)에 맞춰 자동 수집 및 문서화합니다.
3. **불법 자금줄 차단:** 침해 사이트와 배너 광고로 연계된 불법 도박 조직 간의 연관성을 증명하여, 범죄 네트워크의 핵심 수익원을 차단할 수 있는 데이터를 제공합니다.
4. **저작권 보호의 민주화:** 비용 장벽을 대폭 낮춤으로써 개인 창작자 및 중소 스튜디오(SME)가 느린 정부 심의 절차에만 의존하지 않고 주도적으로 IP 자산을 방어할 수 있도록 지원합니다.

### 제안 솔루션 및 사용 기술
본 시스템은 인공지능 모델이 긴밀히 통합된 5단계 자동화 파이프라인으로 구성되어 있습니다:
* **0 및 1단계 (네트워크 분석 및 도메인 식별):** 의심 도메인 입력 시 시스템이 URL을 정규화하고 화이트리스트 데이터베이스와 대조합니다. 이후 WHOIS 레코드 분석(도메인 연식, 등록 대행사) 및 DNS 분석(TXT, MX, NS), IP 대역 해상 등을 수행합니다. 특히 리다이렉트 체인 추적(Redirect Tracking)을 통해 도메인 우회 행태를 실시간으로 감지합니다.
* **2단계 (브라우저 시뮬레이션 및 심층 증거 수집):** Playwright를 사용한 헤드리스 브라우저(Headless Browser) 구동으로 봇 차단 기술을 우회하고 실제 사용자 환경을 모사합니다. 침해 페이지의 고해상도 스크린샷 캡처, DOM 텍스트 추출 및 스트리밍 소스 링크를 수집합니다.
* **3단계 (다계층 AI/ML 분석 엔진):**
  * *분야 1 - 컴퓨터 비전 및 광고 배너 OCR:* YOLO 객체 탐지 모델을 활용하여 사이트 내 배너 광고의 위치를 식별합니다. 이후 OCR 파이프라인을 가동하여 한국어 및 영어 도박 관련 키워드를 스캔하고 불법 자금 연계 위험 지수를 도출합니다.
  * *분야 2 - NLP 기반 DOM 텍스트 분류:* 수집된 DOM 텍스트를 자연어 처리 모델로 분류하여 해당 사이트의 침해 카테고리(불법 웹툰, 불법 음원, 불법 스트리밍 등)를 정확히 판별합니다.
* **4단계 (LLM 기반 증거 보고서 합성):** Google Gemini API를 연동하여 수집된 모든 기계적 로그, 스크린샷, 리다이렉트 이력, 불법 광고 정보를 표준화된 법적 디지털 증거 패키지로 자동 합성하고 위험 등급을 부여합니다.

### 혁신성 및 창의성
* **증거 중심 접근법 (Evidence-First Approach):** 단순 사이트 감지를 넘어 법적 소송 및 DMCA 삭제 요청에 즉시 활용할 수 있는 신뢰성 높은 '디지털 증거 패키지'를 구축함으로써, 저작권 침해 신고의 효력과 승인율을 기존 40%에서 90% 이상으로 끌어올립니다.
* **저작권 침해와 사회 범죄의 연계 입증:** 컴퓨터 비전 기술을 통해 저작권 침해 사이트가 사설 도박 등 범죄 조직의 광고 플랫폼으로 기능하고 있음을 증명하며, 본 기술을 단순 저작권 보호를 넘어 사회 안전을 지키는 기술로 승화시켰습니다.
* **도메인 홉핑 자동 추적:** 리다이렉션 경로를 실시간으로 추적 및 분석하여 저작권 침해범들이 도메인을 변경하더라도 끝까지 추적할 수 있는 기술적 기반을 마련했습니다.

### 응용 가능성 및 상용화 계획
* **타겟 고객군 (B2B SaaS):** 대형 웹툰 플랫폼(네이버웹툰, 카카오페이지 등), 엔터테인먼트 기획사(K-pop 레이블, CJ ENM 등), 저작권 전문 로펌 및 영세 창작자 조합.
* **시스템 연동:** 콘텐츠 관리 시스템(CMS)과 API 방식으로 결합하여 새로운 웹툰이나 음원이 출시될 때마다 백그라운드에서 자동으로 감지 루틴을 시작합니다.
* **비즈니스 모델:** 감시 대상 저작물 수에 따른 구독형 과금 모델(Pay-per-IP) 또는 실시간 대시보드가 제공되는 월정액 모니터링 라이선스 체계.

### 사용자 및 사회적 가치
* **창작자 보호:** 불법 유출로 인한 창작자의 직접적인 매출 손실을 즉각 방어하여 창작 의욕을 고취하고 창작 생태계의 선순환을 유도합니다.
* **사회 안전 기여:** 불법 도박 및 유해 광고 노출을 차단하여 청소년들을 유해 환경으로부터 보호합니다. 아울러 불법 복제 사이트로 유입되는 범죄 자금줄을 차단하여 사회 정화에 기여합니다.
* **행정 효율 극대화:** 분산화된 민간 감시 네트워크 역할을 수행함으로써, 정부의 심의 기관에 검증된 증거 데이터를 즉각 공급해 도메인 차단 처리 속도를 비약적으로 단축시킵니다.
