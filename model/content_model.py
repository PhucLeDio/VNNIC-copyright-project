# =====================================================================
# 1. Cài đặt các thư viện cần thiết trên Colab
# =====================================================================
# Cài đặt Playwright để có thể cào các trang web có cơ chế bảo vệ hoặc dùng Javascript

import re
import asyncio
import requests
import torch
import torch.nn as nn
from typing import List
from collections import Counter
from bs4 import BeautifulSoup
from transformers import AutoConfig, AutoTokenizer, RobertaPreTrainedModel, RobertaModel
from transformers.models.roberta.modeling_roberta import RobertaClassificationHead
from transformers.modeling_outputs import SequenceClassifierOutput
import nest_asyncio # Import nest_asyncio

nest_asyncio.apply() # Apply nest_asyncio to allow nested event loops

# Thiết lập GPU nếu có
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Thiết bị hoạt động: {device}")

# Mappings phân loại
TYPE_MAPPING = {
    -1: "Không hoạt động",
    0:  "Báo chí",
    1:  "18+",
    2:  "Cờ bạc",
    3:  "Vay",
    4:  "Tiền ảo",
    5:  "Tổ chức",
    6:  "E-commerce",
    7:  "MXH",
    8:  "Game",
    9:  "Chưa xác định"
}

# =====================================================================
# 2. Định nghĩa kiến trúc Model PhoBERT Multi-task
# =====================================================================
class PhoBERTMultiTask(RobertaPreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.num_labels_task1 = getattr(config, 'num_labels_task1', 2)
        self.num_labels_task2 = getattr(config, 'num_labels_task2', 10)
        self.config.num_labels = self.num_labels_task1

        self.roberta = RobertaModel(config, add_pooling_layer=False)
        self.classifier_task1 = RobertaClassificationHead(config)
        self.classifier_task2 = nn.Sequential(
            nn.Linear(config.hidden_size, 768),
            nn.ReLU(),
            nn.Linear(768, 1024),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(1024, self.num_labels_task2)
        )
        self.post_init()

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, task_id=2):
        outputs = self.roberta(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True,
        )
        sequence_output = outputs.last_hidden_state
        cls_emb = sequence_output[:, 0, :]

        if task_id == 1:
            logits = self.classifier_task1(sequence_output)
        else:
            logits = self.classifier_task2(cls_emb)

        return SequenceClassifierOutput(logits=logits)

# =====================================================================
# 3. Hàm cào dữ liệu DOM (Giả lập chiến lược 2 tầng)
# =====================================================================
def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

async def crawl_domain_html(url: str) -> str:
    target_url = normalize_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # ---- TẦNG 1: Thử cào nhanh bằng HTTP Request thông thường ----
    print(f"[Tier 1] Đang tải nhanh URL bằng HTTP Request: {target_url}")
    try:
        response = requests.get(target_url, headers=headers, timeout=10, verify=False)
        if response.status_code == 200 and len(response.text) > 1000:
            print(" -> Tier 1 thành công!")
            return response.text
        else:
            print(f" -> Tier 1 trả về mã lỗi {response.status_code} hoặc nội dung quá ngắn. Chuyển sang Tier 2...")
    except Exception as e:
        print(f" -> Tier 1 thất bại do lỗi kết nối: {e}. Chuyển sang Tier 2...")

    # ---- TẦNG 2: Khởi chạy trình duyệt thật Playwright để cào ----
    print(f"[Tier 2] Đang khởi động trình duyệt để cào: {target_url}")
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Giả lập User-Agent của Chrome
            await page.set_extra_http_headers(headers)
            await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)

            # Đợi thêm 1 chút phòng trường hợp trang dùng JS để load động
            await asyncio.sleep(2)
            html = await page.content()
            await browser.close()
            print(" -> Tier 2 thành công!")
            return html
    except Exception as e:
        print(f" -> Tier 2 thất bại: {e}")
        raise RuntimeError(f"Không thể cào dữ liệu từ tên miền {url} bằng cả 2 phương thức.")

# =====================================================================
# 4. Các hàm xử lý văn bản (Làm sạch & Phân đoạn)
# =====================================================================
def get_clean_text_from_html(html_content: str) -> str:
    if not html_content: return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe", "svg", "aside", "form", "button"]):
        tag.decompose()
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote", "pre", "article", "section", "br"]):
        tag.insert_before("\n")
    text = soup.get_text(separator="", strip=False)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if re.sub(r"[ \t]+", " ", line).strip()]
    return "\n".join(lines).strip()

def segment_content(content: str, max_words: int = 256, overlap_words: int = 40) -> List[str]:
    if not content or not isinstance(content, str): return []
    text = re.sub(r"\s+", " ", content.strip())
    try:
        from pyvi import ViTokenizer
        words, _ = ViTokenizer.spacy_tokenize(text)
    except Exception:
        words = text.split()

    if len(words) <= max_words:
        return [" ".join(words).replace("_", " ")]

    segments = []
    start = 0
    while start < len(words):
        end = start + max_words
        if end >= len(words):
            segment_words = words[start:]
            start = len(words)
        else:
            cutoff = end
            search_from = max(start, end - 100)
            for i in range(end - 1, search_from - 1, -1):
                word = words[i].replace("_", " ")
                if any(word.endswith(p) for p in ".!?。！？\n"):
                    cutoff = i + 1
                    break
            segment_words = words[start:cutoff]
            start = max(cutoff - overlap_words, 0)

        segment_text = " ".join(segment_words).replace("_", " ").strip()
        if len(segment_text) > 30:
            segments.append(segment_text)
    return segments

# =====================================================================
# 5. Tải Model & Tokenizer từ Hugging Face
# =====================================================================
MODEL_NAME = "phucleDio/finetune_cls_vs_content_12class_v5"
TOKENIZER_NAME = "vinai/phobert-base"

print("\n--- Đang tải mô hình từ Hugging Face (Có thể mất vài phút)... ---")
config = AutoConfig.from_pretrained(MODEL_NAME)
model = PhoBERTMultiTask.from_pretrained(MODEL_NAME, config=config).to(device)
model.eval()

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
print("--- Tải mô hình thành công! ---")

# =====================================================================
# 6. Pipeline Tích Hợp Dự Đoán Từ Tên Miền
# =====================================================================
async def run_pipeline_for_domain(domain_url: str, mode: str = "quick"):
    print("\n" + "="*70)
    print(f"BẮT ĐẦU ĐÁNH GIÁ TRANG: {domain_url}")
    print("="*70)

    try:
        # B1: Cào HTML
        html_content = await crawl_domain_html(domain_url)

        # B2: Làm sạch
        cleaned_text = get_clean_text_from_html(html_content)

        # B3: Phân đoạn
        segments = segment_content(cleaned_text, max_words=256, overlap_words=40)
        print(f"\nPhát hiện {len(segments)} phân đoạn để phân tích.")
        if not segments:
            print("Không trích xuất được văn bản chính thức từ trang web.")
            return

        phishing_detected = False
        flagged_segment = ""
        phishing_idx = None
        type_votes = []

        # B4: Chạy Model AI phân tích từng segment
        for idx, seg in enumerate(segments):
            inputs = tokenizer(seg, truncation=True, max_length=256, padding="max_length", return_tensors="pt").to(device)

            with torch.no_grad():
                # Tác vụ 1: Độc hại
                outputs_task1 = model(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"], task_id=1)
                pred_label = int(torch.softmax(outputs_task1.logits, dim=-1).cpu().argmax(dim=-1)[0])

                # Tác vụ 2: Thể loại
                outputs_task2 = model(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"], task_id=2)
                pred_type = int(torch.softmax(outputs_task2.logits, dim=-1).cpu().argmax(dim=-1)[0])

            type_votes.append(pred_type)
            print(f" > Segment {idx+1}: Nhãn={pred_label} (1 là Độc hại), Loại={TYPE_MAPPING.get(pred_type, 'Chưa xác định')}")

            if pred_label == 1:
                if not flagged_segment:
                    flagged_segment = seg
                    phishing_idx = idx + 1
                phishing_detected = True
                if mode == "quick":
                    print(" [Early Stop] Phát hiện nội dung độc hại! Dừng quét các segment tiếp theo.")
                    break

        # B5: Biểu quyết thể loại website chung
        if not type_votes:
            final_type = 9
        else:
            counter = Counter(type_votes)
            ranked = counter.most_common()
            without_9 = [x for x in ranked if x[0] != 9]
            if 9 in counter:
                without_9.append((9, counter[9]))
            final_type = without_9[0][0] if without_9 else 9

        print("\n" + "="*50)
        print("KẾT QUẢ ĐÁNH GIÁ CUỐI CÙNG:")
        print(f" - Tên miền: {domain_url}")
        print(f" - Kết quả độc hại: {'ĐỘC HẠI (Phishing)' if phishing_detected else 'AN TOÀN'}")
        print(f" - Thể loại website: {TYPE_MAPPING.get(final_type)}")
        if phishing_detected:
            print(f" - Bị phát hiện tại phân đoạn: {phishing_idx}")
            print(f" - Đoạn văn bản vi phạm: \"{flagged_segment[:150]}...\"")
        print("="*50)

    except Exception as e:
        print(f"Lỗi hệ thống trong quá trình xử lý: {e}")

# =====================================================================
# 7. Nhập tên miền cần kiểm tra vào đây và khởi chạy
# =====================================================================
# Bạn hãy thay thế bằng bất kỳ tên miền nào bạn muốn test thử
domain_to_test = "tuoitre.vn"  # Ví dụ: tuoitre.vn, vnexpress.net, shopee.vn...
asyncio.run(run_pipeline_for_domain(domain_to_test, mode="quick"))