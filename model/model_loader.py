"""
model/model_loader.py

Lazy singleton loader cho Domain Model và Content Model.
- Model chỉ được tải xuống 1 lần duy nhất (singleton pattern).
- Thread-safe với threading.Lock.
"""

import threading
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import (
    RobertaModel,
    RobertaPreTrainedModel,
    AutoTokenizer,
    AutoConfig,
)
from transformers.models.roberta.modeling_roberta import RobertaClassificationHead
from transformers.modeling_outputs import SequenceClassifierOutput

# ==============================================================================
# KIẾN TRÚC DOMAIN MODEL
# ==============================================================================

class FocalLoss(nn.Module):
    def __init__(self, alpha=1.5, gamma=2.0, reduction="mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits, labels):
        ce_loss = F.cross_entropy(logits, labels, reduction="none")
        pt = torch.exp(-ce_loss)
        loss = self.alpha * (1 - pt) ** self.gamma * ce_loss
        return loss.mean() if self.reduction == "mean" else loss.sum()


class HybridFeaturesDomain(RobertaPreTrainedModel):
    """
    Domain model: kết hợp 12 lexical features + PhoBERT encoding.
    Input : domain str + features list[float] (độ dài 12)
    Output: label 0 = An toàn / 1 = Độc hại
    """

    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.config.num_classes = 2
        self.num_features = 12
        self._tied_weights_keys = []
        self.roberta = RobertaModel(config, add_pooling_layer=False)

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

    def forward(
        self,
        features,
        input_ids,
        attention_mask,
        token_type_ids=None,
        labels=None,
    ):
        x_nn = self.fc1(features)
        x_lexical = self.fc2(x_nn)

        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            output_hidden_states=True,
        )
        hidden_states = torch.stack(outputs.hidden_states[-1:], dim=0)
        x_roberta = torch.mean(hidden_states, dim=0)
        x_roberta = torch.mean(x_roberta, dim=1)

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
# KIẾN TRÚC CONTENT MODEL
# ==============================================================================

class PhoBERTMultiTask(RobertaPreTrainedModel):
    """
    Content model: multi-task PhoBERT.
    Task 1 (task_id=1): label 0 = An toàn / 1 = Độc hại
    Task 2 (task_id=2): loại website (0-8)
    """

    def __init__(self, config):
        super().__init__(config)
        self.num_labels_task1 = getattr(config, "num_labels_task1", 2)
        self.num_labels_task2 = getattr(config, "num_labels_task2", 8)
        self.config.num_labels = self.num_labels_task1

        self.roberta = RobertaModel(config, add_pooling_layer=False)
        self.classifier_task1 = RobertaClassificationHead(config)
        self.classifier_task2 = nn.Sequential(
            nn.Linear(config.hidden_size, 768),
            nn.ReLU(),
            nn.Linear(768, 1024),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(1024, self.num_labels_task2),
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

        logits = (
            self.classifier_task1(sequence_output)
            if task_id == 1
            else self.classifier_task2(cls_emb)
        )

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
# LAZY SINGLETON LOADERS
# ==============================================================================

_DOMAIN_MODEL_NAME  = "ttqdunggg/hybrid_feats_domain"
_CONTENT_MODEL_NAME = "ttqdunggg/finetune_cls_vs_content_ronbackbone_100k"
_PHOBERT_TOKENIZER  = "vinai/phobert-base"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- Domain model state ---
_domain_model: HybridFeaturesDomain | None = None
_domain_tokenizer = None
_domain_lock = threading.Lock()

# --- Content model state ---
_content_model: PhoBERTMultiTask | None = None
_content_tokenizer = None
_content_lock = threading.Lock()


def get_domain_model():
    """
    Trả về (model, tokenizer) của Domain Model.
    Chỉ tải lần đầu tiên gọi (lazy singleton).
    """
    global _domain_model, _domain_tokenizer
    if _domain_model is None:
        with _domain_lock:
            if _domain_model is None:
                print("[ModelLoader] Đang tải Domain Model từ Hugging Face...")
                config = AutoConfig.from_pretrained(_DOMAIN_MODEL_NAME)
                _domain_model = HybridFeaturesDomain.from_pretrained(
                    _DOMAIN_MODEL_NAME, config=config
                )
                _domain_model.eval().to(DEVICE)
                _domain_tokenizer = AutoTokenizer.from_pretrained(_PHOBERT_TOKENIZER)
                print("[ModelLoader] ✅ Domain Model đã sẵn sàng.")
    return _domain_model, _domain_tokenizer


def get_content_model():
    """
    Trả về (model, tokenizer) của Content Model.
    Chỉ tải lần đầu tiên gọi (lazy singleton).
    """
    global _content_model, _content_tokenizer
    if _content_model is None:
        with _content_lock:
            if _content_model is None:
                print("[ModelLoader] Đang tải Content Model từ Hugging Face...")
                config = AutoConfig.from_pretrained(_CONTENT_MODEL_NAME)
                _content_model = PhoBERTMultiTask.from_pretrained(
                    _CONTENT_MODEL_NAME, config=config
                )
                _content_model.eval().to(DEVICE)
                _content_tokenizer = AutoTokenizer.from_pretrained(_PHOBERT_TOKENIZER)
                print("[ModelLoader] ✅ Content Model đã sẵn sàng.")
    return _content_model, _content_tokenizer
