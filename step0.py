"""
Step 0: Whitelist Processing
This script will implement the whitelist CSV parsing and domain filtering logic.
"""
from urllib.parse import urlparse
import pandas as pd
import re


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