# ==============================================================================
# 1. Cài đặt thư viện cần thiết
# ==============================================================================

import torch
import torch.nn as nn
from transformers import RobertaModel, RobertaPreTrainedModel, AutoTokenizer, AutoConfig
from transformers.models.roberta.modeling_roberta import RobertaClassificationHead
from transformers.modeling_outputs import SequenceClassifierOutput

# ==============================================================================
# 2. Định nghĩa cấu trúc mô hình PhoBERTMultiTask
# ==============================================================================
class PhoBERTMultiTask(RobertaPreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.num_labels_task1 = getattr(config, 'num_labels_task1', 2)
        self.num_labels_task2 = getattr(config, 'num_labels_task2', 8)
        self.config.num_labels = self.num_labels_task1

        # Shared encoder (PhoBERT)
        self.roberta = RobertaModel(config, add_pooling_layer=False)

        # Task 1: Head phân loại nhãn nhạy cảm/độc hại
        self.classifier_task1 = RobertaClassificationHead(config)

        # Task 2: Head phân loại danh mục trang web (Cờ bạc, 18+, Vay, ...)
        self.classifier_task2 = nn.Sequential(
            nn.Linear(config.hidden_size, 768),
            nn.ReLU(),
            nn.Linear(768, 1024),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(1024, self.num_labels_task2)
        )
        self.post_init()

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        task_id=2,
        labels=None,
        output_attentions=None,
        output_hidden_states=None,
        return_dict=None,
    ):
        outputs = self.roberta(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            output_attentions=output_attentions,
            output_hidden_states=True,
            return_dict=True,
        )

        sequence_output = outputs.last_hidden_state
        cls_emb = sequence_output[:, 0, :]

        if task_id == 1:
            logits = self.classifier_task1(sequence_output)
        else:
            logits = self.classifier_task2(cls_emb)

        loss = None
        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, logits.size(-1)), labels.view(-1))

        return SequenceClassifierOutput(
            loss=loss,
            logits=logits,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions,
        )

# ==============================================================================
# 3. Khởi tạo Model, Tokenizer và cấu hình thiết bị chạy
# ==============================================================================
MODEL_NAME = "ttqdunggg/finetune_cls_vs_content_ronbackbone_100k"
TOKENIZER_NAME = "vinai/phobert-base"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Đang sử dụng thiết bị: {device}")
print("Đang tải cấu hình và trọng số mô hình từ Hugging Face...")

config = AutoConfig.from_pretrained(MODEL_NAME)
model = PhoBERTMultiTask.from_pretrained(MODEL_NAME, config=config)
model.eval().to(device)

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
print("✅ Tải mô hình và Tokenizer thành công!")

# Mapping danh mục kết quả Task 2
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
    9:  "Chưa xác định",
}

# ==============================================================================
# 4. Định nghĩa hàm dự đoán song song 2 task
# ==============================================================================
@torch.no_grad()
def predict_both_tasks(text: str) -> dict:
    enc = tokenizer(
        text,
        truncation=True,
        max_length=256,
        padding="max_length",
        return_tensors="pt",
    )
    input_ids = enc["input_ids"].to(device)
    attention_mask = enc["attention_mask"].to(device)

    # 1. Dự đoán Task 1 (Phishing / Credibility)
    out_task1 = model(input_ids=input_ids, attention_mask=attention_mask, task_id=1)
    probs_1 = torch.softmax(out_task1.logits, dim=-1).cpu().numpy()[0]
    label_1 = int(probs_1.argmax())

    # 2. Dự đoán Task 2 (Website Category)
    out_task2 = model(input_ids=input_ids, attention_mask=attention_mask, task_id=2)
    probs_2 = torch.softmax(out_task2.logits, dim=-1).cpu().numpy()[0]
    label_2 = int(probs_2.argmax())

    return {
        "label": label_1,
        "label_name": "Độc hại / Phishing" if label_1 == 1 else "An toàn",
        "type": label_2,
        "type_name": TYPE_MAPPING.get(label_2, "Chưa xác định"),
        "model": "v2_multitask"
    }

# ==============================================================================
# 5. Chạy thử nghiệm mẫu
# ==============================================================================
sample_text = "Chào mừng bạn đến với cổng game bài đổi thưởng, nạp rút 1-1 nhanh chóng cực kỳ uy tín!"
print(f"\nDự đoán cho nội dung: '{sample_text}'")
result = predict_both_tasks(sample_text)

print("-" * 50)
print(f"Nhãn độc hại (Task 1): {result['label']} ({result['label_name']})")
print(f"Loại website  (Task 2): {result['type']} ({result['type_name']})")
print("-" * 50)
