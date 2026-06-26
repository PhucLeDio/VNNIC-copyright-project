"""
Step 0: Whitelist Processing + Domain Model Pre-screening

Bước 0 thực hiện 2 công việc:
  1. Whitelist Check : kiểm tra domain trong VNNIC whitelist database
  2. Domain Model    : chạy HybridFeaturesDomain (PhoBERT + 12 lexical features)
                       để phân loại sơ bộ domain là An toàn hay Độc hại

Kết quả sẽ gắn flag FLAG_TRUST_HIGH (whitelist match) hoặc
FLAG_DOMAIN_PREDICT_MALICIOUS (domain model predict 1).
"""
from urllib.parse import urlparse
import math
import sys
import os
import torch
import pandas as pd
import re

# Thêm thư mục model vào sys.path để import model_loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model"))
from model_loader import get_domain_model, DEVICE


def normalize_domain(url: str) -> str:

    if not url or pd.isna(url):
        return ""

    url = str(url).strip().lower().strip(".").strip("/")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:

        parsed = urlparse(url)

        domain = parsed.netloc

        if not domain:
            domain = parsed.path.split("/")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        domain = domain.split(":")[0].strip(".")

        return domain

    except:

        return ""


def extract_domains_from_cell(value) -> list:

    if not value or pd.isna(value):
        return []

    text = str(value).lower()

    text = text.replace(" và ", ",")

    parts = re.split(r'[;,\s]+', text)

    domains = []

    for part in parts:

        part = part.strip().strip(".").strip("/")

        if not part:
            continue

        if not part.startswith(("http://", "https://")):
            norm = normalize_domain("https://" + part)

        else:

            norm = normalize_domain(part)

        if norm:
            domains.append(norm)

    return domains


def load_domain_database(csv_path):

    df = pd.read_csv(csv_path)

    domains = set()

    col_name = "Địa chỉ tên miền"

    if col_name in df.columns:

        col_data = df[col_name]

    else:

        col_data = df.iloc[:, 4] if df.shape[1] > 4 else df.iloc[:, 0]

    for value in col_data:

        extracted = extract_domains_from_cell(value)

        for d in extracted:
            domains.add(d)

    return domains


def is_domain_whitelisted(domain, whitelist_set):

    if not domain:
        return False

    domain = domain.lower().strip(".")

    if domain in whitelist_set:
        return True

    parts = domain.split(".")

    for i in range(1, len(parts) - 1):

        parent = ".".join(parts[i:])

        if parent in whitelist_set:
            return True

    return False


def check_domain_in_database(
        input_domain,
        csv_path
):

    db = load_domain_database(csv_path)

    normalized = normalize_domain(input_domain)

    found = is_domain_whitelisted(normalized, db)

    return {
        "input_domain": input_domain,
        "normalized_domain": normalized,
        "in_database": found
    }


# ==============================================================================
# DOMAIN FEATURE EXTRACTION (12 features cho Domain Model)
# ==============================================================================

def _shannon_entropy(s: str) -> float:
    """Tính Shannon entropy của chuỗi ký tự."""
    if not s:
        return 0.0
    freq = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    n = len(s)
    return -sum((f / n) * math.log2(f / n) for f in freq.values())


def extract_domain_features(domain: str, step1_evidence: dict | None = None) -> list[float]:
    """
    Tính 12 lexical + hosting features từ domain và step1 evidence.

    Thứ tự features (phải giống lúc train Domain Model):
    [0]  domain_length     : số ký tự trong domain
    [1]  entropy           : Shannon entropy của chuỗi domain
    [2]  percentage_digits : tỉ lệ ký tự số (0.0 - 1.0)
    [3]  special_chars     : số ký tự đặc biệt (-, _) trong domain
    [4]  is_cheap_tld      : 1 nếu TLD có risk HIGH, 0 ngược lại
    [5]  passive_dns_len   : số bản ghi A (DNS)
    [6]  unique_addresses  : số IP duy nhất
    [7]  unique_hostnames  : số bản ghi NS
    [8]  asn_switch        : 1 nếu là suspicious hosting
    [9]  ip_count          : tổng số IP
    [10] subdomain_depth   : số phần của domain (dấu chấm + 1)
    [11] ttl_value         : TTL (fallback 300.0 nếu không có)

    Args:
        domain       : Normalized domain string (e.g. "example.com")
        step1_evidence: dict từ build_evidence_buffer() — dùng để lấy
                        DNS records, IPs, hosting info. Có thể là None
                        nếu chưa chạy step1 (sẽ dùng giá trị mặc định).

    Returns:
        list[float] gồm 12 giá trị theo đúng thứ tự trên.
    """
    e = step1_evidence or {}

    # --- Feature 0: domain_length ---
    domain_length = float(len(domain))

    # --- Feature 1: entropy ---
    entropy = _shannon_entropy(domain)

    # --- Feature 2: percentage_digits ---
    digit_count = sum(1 for c in domain if c.isdigit())
    percentage_digits = digit_count / len(domain) if domain else 0.0

    # --- Feature 3: special_chars ---
    special_chars = float(sum(1 for c in domain if c in "-_"))

    # --- Feature 4: is_cheap_tld ---
    tld_info = e.get("tld_info", {})
    is_cheap_tld = 1.0 if tld_info.get("risk") == "HIGH" else 0.0

    # --- Feature 5: passive_dns_len ---
    dns_records = e.get("dns_records", {})
    passive_dns_len = float(len(dns_records.get("A", [])))

    # --- Feature 6: unique_addresses ---
    resolved_ips = e.get("resolved_ip", [])
    unique_addresses = float(len(set(resolved_ips)))

    # --- Feature 7: unique_hostnames ---
    unique_hostnames = float(len(dns_records.get("NS", [])))

    # --- Feature 8: asn_switch ---
    asn_switch = 1.0 if e.get("suspicious_hosting", False) else 0.0

    # --- Feature 9: ip_count ---
    ip_count = float(len(resolved_ips))

    # --- Feature 10: subdomain_depth ---
    subdomain_depth = float(len(domain.split(".")))

    # --- Feature 11: ttl_value (fallback 300.0) ---
    ttl_value = 300.0

    return [
        domain_length,
        entropy,
        percentage_digits,
        special_chars,
        is_cheap_tld,
        passive_dns_len,
        unique_addresses,
        unique_hostnames,
        asn_switch,
        ip_count,
        subdomain_depth,
        ttl_value,
    ]


# ==============================================================================
# DOMAIN MODEL INFERENCE
# ==============================================================================

@torch.no_grad()
def run_domain_model_check(domain: str, step1_evidence: dict | None = None) -> dict:
    """
    Chạy Domain Model để phân loại domain.

    Args:
        domain        : Normalized domain string.
        step1_evidence: Evidence dict từ Step 1 (build_evidence_buffer).
                        Nếu None, features sẽ dùng giá trị mặc định.

    Returns:
        dict: {
            "label"      : int  (0=An toàn / 1=Độc hại),
            "label_name" : str,
            "prob_safe"  : float,
            "prob_malicious": float,
            "features"   : list[float],  # 12 features đã dùng
            "flag"       : str,  # "FLAG_DOMAIN_PREDICT_MALICIOUS" hoặc "OK"
            "model"      : str,
        }
    """
    model, tokenizer = get_domain_model()

    features = extract_domain_features(domain, step1_evidence)
    feat_tensor = torch.tensor([features], dtype=torch.float32).to(DEVICE)

    enc = tokenizer(
        domain,
        truncation=True,
        max_length=256,
        padding="max_length",
        return_tensors="pt",
    )
    input_ids      = enc["input_ids"].to(DEVICE)
    attention_mask = enc["attention_mask"].to(DEVICE)

    out    = model(features=feat_tensor, input_ids=input_ids, attention_mask=attention_mask)
    probs  = torch.softmax(out.logits, dim=-1).cpu().numpy()[0]
    label  = int(probs.argmax())

    return {
        "label":          label,
        "label_name":     "Độc hại" if label == 1 else "An toàn",
        "prob_safe":      round(float(probs[0]), 4),
        "prob_malicious": round(float(probs[1]), 4),
        "features":       features,
        "flag":           "FLAG_DOMAIN_PREDICT_MALICIOUS" if label == 1 else "OK",
        "model":          "v1_hybrid",
    }