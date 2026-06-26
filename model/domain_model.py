# ==============================================================================
# 1. Cài đặt thư viện cần thiết (nếu Colab chưa có)
# ==============================================================================

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import RobertaModel, RobertaPreTrainedModel, AutoTokenizer, AutoConfig
from transformers.modeling_outputs import SequenceClassifierOutput

# ==============================================================================
# 2. Định nghĩa kiến trúc mô hình (FocalLoss & HybridFeaturesDomain)
# ==============================================================================
class FocalLoss(nn.Module):
    def __init__(self, alpha=1.5, gamma=2.0, reduction='mean'):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits, labels):
        ce_loss = F.cross_entropy(logits, labels, reduction='none')
        pt = torch.exp(-ce_loss)
        loss = self.alpha * (1 - pt) ** self.gamma * ce_loss
        if self.reduction == 'mean':
            return loss.mean()
        else:
            return loss.sum()

class HybridFeaturesDomain(RobertaPreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.config.num_classes = 2
        self.num_features = 12
        self._tied_weights_keys = []
        self.roberta = RobertaModel(config, add_pooling_layer=False)

        # Lexical feature branch
        self.fc1 = nn.Sequential(
            nn.BatchNorm1d(self.num_features),
            nn.Linear(self.num_features, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
        )
        self.fc2 = nn.Sequential(
            nn.Linear(256, 768),
            nn.ReLU(),
            nn.Dropout(0.1),
        )

        self.out_aux = nn.Linear(256, 2)
        self.dropout_lm = nn.Dropout(0.1)
        self.out_main = nn.Linear(768 * 2, 2)

        self.init_weights()
        self.loss_fct = FocalLoss(alpha=1.5, gamma=2.0)

    @property
    def all_tied_weights_keys(self):
        return {}

    def forward(self, features, input_ids, attention_mask, token_type_ids=None, labels=None):
        # 1. Nhánh Lexical Features
        x_nn = self.fc1(features)
        x_lexical = self.fc2(x_nn)

        # 2. Nhánh PhoBERT
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            output_hidden_states=True,
        )

        # Lấy hidden states layer cuối cùng
        hidden_states = torch.stack(outputs.hidden_states[-1:], dim=0)  # [1, batch, seq, hidden]
        x_roberta = torch.mean(hidden_states, dim=0)  # [batch, seq, hidden]
        x_roberta = torch.mean(x_roberta, dim=1)

        # 3. Kết hợp (Fusion)
        x_roberta = self.dropout_lm(x_roberta)
        x_concat = torch.cat((x_lexical, x_roberta), dim=1)

        logits_main = self.out_main(x_concat)
        logits_aux = self.out_aux(x_nn)

        loss = None
        if labels is not None:
            if labels.dtype != torch.long:
                labels = labels.to(torch.long)
            loss_main = self.loss_fct(logits_main, labels)
            loss_aux = self.loss_fct(logits_aux, labels)
            loss = loss_main + 0.3 * loss_aux

        return SequenceClassifierOutput(loss=loss, logits=logits_main)

# ==============================================================================
# 3. Khởi tạo Model, Tokenizer và cấu hình thiết bị chạy (CPU/CUDA)
# ==============================================================================
MODEL_NAME = "ttqdunggg/hybrid_feats_domain"
TOKENIZER_NAME = "vinai/phobert-base"
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Đang sử dụng thiết bị: {device}")
print("Đang tải cấu hình và trọng số mô hình từ Hugging Face...")

config = AutoConfig.from_pretrained(MODEL_NAME)
# Đăng ký class HybridFeaturesDomain vào thư viện để transformers nhận diện được
model = HybridFeaturesDomain.from_pretrained(MODEL_NAME, config=config)
model.eval().to(device)

tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
print("✅ Tải mô hình và Tokenizer thành công!")

# ==============================================================================
# 4. Định nghĩa hàm dự đoán
# ==============================================================================
@torch.no_grad()
def predict_domain_v1(domain: str, features: list) -> dict:
    """
    domain   : str  (tên miền đã xử lý)
    features : list[float] có độ dài 12
    """
    # Chuyển đổi features sang tensor
    feat_tensor = torch.tensor([features], dtype=torch.float32).to(device)

    # Tokenize tên miền
    enc = tokenizer(
        domain,
        truncation=True,
        max_length=256,
        padding="max_length",
        return_tensors="pt",
    )
    input_ids = enc["input_ids"].to(device)
    attention_mask = enc["attention_mask"].to(device)

    # Chạy inference qua model
    out = model(
        features=feat_tensor,
        input_ids=input_ids,
        attention_mask=attention_mask,
    )
    logits = out.logits
    probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
    label = int(probs.argmax())

    return {
        "logits": logits.cpu().numpy().tolist(),
        "probabilities": probs.tolist(),
        "label": label,                          # 0 = An toàn / Bình thường, 1 = Độc hại / Tín nhiệm thấp
        "label_name": "Độc hại" if label == 1 else "An toàn",
        "model": "v1_hybrid"
    }

# ==============================================================================
# 5. Chạy thử nghiệm với dữ liệu giả lập (Demo)
# ==============================================================================
# Tên miền test
test_domain = "facebook.com"

# Vector 12 đặc trưng lexical & hosting features:
# Order: domain_length, entropy, percentage_digits, special_chars, is_cheap_tld,
#        passive_dns_len, unique_addresses, unique_hostnames, asn_switch, ip_count, subdomain_depth, ttl_value
test_features = [12.0, 3.2, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 300.0]

print(f"\nDự đoán cho tên miền: {test_domain}")
result = predict_domain_v1(test_domain, test_features)

print("-" * 50)
print(f"Xác suất: Safe: {result['probabilities'][0]:.4f} | Phishing: {result['probabilities'][1]:.4f}")
print(f"Nhãn dự đoán: {result['label']} ({result['label_name']})")
print("-" * 50)
