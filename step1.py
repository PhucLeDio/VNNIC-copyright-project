"""
Step 1: Web Crawling and Evidence Gathering
This script will implement the DeepCrawler and network/iframe analysis logic.
"""
# step1.py

import ssl
import socket
import hashlib
import requests
import whois
import dns.resolver

from datetime import datetime, timezone
from ipwhois import IPWhois


#################################################
# CONFIG
#################################################

HIGH_RISK_TLDS = {
    ".xyz",
    ".top",
    ".cc",
    ".to"
}

MEDIUM_RISK_TLDS = {
    ".tv",
    ".live",
    ".vip",
    ".fun",
    ".icu"
}

HIGH_RISK_REGISTRARS = {
    "namecheap",
    "namesilo",
    "njalla"
}

MAJOR_CLOUD_PROVIDERS = {
    "amazon": "AWS",
    "google": "GCP",
    "microsoft": "AZURE",
    "cloudflare": "CLOUDFLARE",
    "akamai": "AKAMAI"
}

SUSPICIOUS_HOSTING = {
    "ovh",
    "hetzner",
    "digitalocean",
    "vultr",
    "hostinger",
    "contabo"
}

OFFICIAL_TLDS = {
    ".vn", ".gov", ".edu",
    ".org", ".ac", ".go"
}


#################################################
# HELPERS
#################################################

def safe_lower(value):

    if value is None:
        return ""

    return str(value).lower()


#################################################
# WHOIS
#################################################

def whois_profile(domain):

    result = {

        "registrar": None,

        "registrar_risk": "UNKNOWN",

        "creation_date": None,

        "domain_age_days": None,

        "privacy_enabled": False
    }

    try:

        w = whois.whois(domain)

        creation = w.creation_date

        if isinstance(creation, list):
            creation = creation[0]

        result["creation_date"] = str(creation)

        if creation:

            if creation.tzinfo is None:

                creation = creation.replace(
                    tzinfo=timezone.utc
                )

            result["domain_age_days"] = (
                datetime.now(timezone.utc)
                - creation
            ).days

        registrar = w.registrar

        result["registrar"] = registrar

        if registrar:

            registrar_lower = registrar.lower()

            if any(
                x in registrar_lower
                for x in HIGH_RISK_REGISTRARS
            ):

                result["registrar_risk"] = "HIGH"

            else:

                result["registrar_risk"] = "LOW"

        raw = str(w).lower()

        privacy_keywords = [

            "privacy",

            "whoisguard",

            "redacted",

            "domains by proxy",

            "privacy protect"
        ]

        result["privacy_enabled"] = any(
            k in raw
            for k in privacy_keywords
        )

    except Exception as e:

        result["error"] = str(e)

    return result


#################################################
# TLD
#################################################

def tld_risk(domain):

    domain = domain.lower()

    for tld in HIGH_RISK_TLDS:

        if domain.endswith(tld):

            return {
                "tld": tld,
                "risk": "HIGH"
            }

    for tld in MEDIUM_RISK_TLDS:

        if domain.endswith(tld):

            return {
                "tld": tld,
                "risk": "MEDIUM"
            }

    return {
        "tld": "." + domain.split(".")[-1],
        "risk": "LOW"
    }


#################################################
# REDIRECTS
#################################################

def track_redirects(url):

    headers = {
        "User-Agent":
            "Mozilla/5.0"
    }

    try:

        r = requests.head(
            url,
            allow_redirects=True,
            timeout=10,
            headers=headers
        )

        if r.status_code >= 400:
            raise Exception()

    except:

        try:

            r = requests.get(
                url,
                allow_redirects=True,
                timeout=10,
                stream=True,
                headers=headers
            )

        except:

            return []

    history = []

    for h in r.history:
        history.append(h.url)

    history.append(r.url)

    return history


def redirect_intelligence(history):

    domains = []

    for url in history:

        try:

            d = (
                url.split("//")[1]
                .split("/")[0]
            )

            domains.append(d)

        except:
            pass

    return {

        "redirect_depth":
            len(history),

        "domains_seen":
            domains,

        "domain_hopping":
            len(set(domains)) > 1
    }


#################################################
# DNS
#################################################

def query_record(domain, record_type):

    try:

        answers = dns.resolver.resolve(
            domain,
            record_type
        )

        return [
            str(x)
            for x in answers
        ]

    except:

        return []


def dns_profile(domain):

    return {

        "A":
            query_record(domain, "A"),

        "AAAA":
            query_record(domain, "AAAA"),

        "NS":
            query_record(domain, "NS"),

        "MX":
            query_record(domain, "MX"),

        "TXT":
            query_record(domain, "TXT"),

        "CNAME":
            query_record(domain, "CNAME")
    }


#################################################
# CDN
#################################################

CDN_SIGNATURES = {

    "cloudflare": [
        "cloudflare"
    ],

    "fastly": [
        "fastly"
    ],

    "akamai": [
        "akam"
    ],

    "bunnycdn": [
        "bunny",
        "b-cdn"
    ],

    "gcore": [
        "gcore"
    ],

    "ddos-guard": [
        "ddos-guard"
    ]
}


def detect_cdn(ns_records):

    detected = []

    joined = " ".join(
        ns_records
    ).lower()

    for provider, patterns in (
        CDN_SIGNATURES.items()
    ):

        if any(
            p in joined
            for p in patterns
        ):

            detected.append(provider)

    return detected


#################################################
# HTTP HEADER FINGERPRINT
#################################################

def http_fingerprint(url):

    result = {}

    try:

        r = requests.get(
            url,
            timeout=10,
            stream=True,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )

        interesting = [

            "Server",

            "CF-Ray",

            "CF-Cache-Status",

            "X-Powered-By",

            "Via",

            "Alt-Svc"
        ]

        for key in interesting:

            if key in r.headers:

                result[key] = (
                    r.headers[key]
                )

    except Exception as e:

        result["error"] = str(e)

    return result


#################################################
# MX
#################################################

def analyze_mx(mx_records):

    return {

        "has_mx":
            len(mx_records) > 0,

        "possible_streaming_only_site":
            len(mx_records) == 0
    }


#################################################
# CLOUD PROVIDER DETECTION
#################################################

def detect_cloud_provider(asn_desc):

    if not asn_desc:
        return None

    text = asn_desc.lower()

    for keyword, provider in (
        MAJOR_CLOUD_PROVIDERS.items()
    ):

        if keyword in text:
            return provider

    return None


def is_suspicious_hosting(asn_desc):

    if not asn_desc:
        return False

    text = asn_desc.lower()

    return any(
        h in text
        for h in SUSPICIOUS_HOSTING
    )


#################################################
# TXT VERIFICATION ANALYSIS
#################################################

def analyze_txt_records(txt_records):

    txt = " ".join(
        txt_records
    ).lower()

    google_count = txt.count(
        "google-site-verification"
    )

    return {

        "google_verification":
            google_count > 0,

        "google_verification_count":
            google_count,

        "spf_configured":
            "v=spf1" in txt,

        "dmarc_configured":
            "v=dmarc1" in txt,

        "microsoft_verification":
            "ms=" in txt,

        "facebook_verification":
            "facebook-domain-verification"
            in txt
    }


#################################################
# MAIL PROVIDER CLASSIFICATION
#################################################

def classify_mail_provider(mx_records):

    if not mx_records:
        return None

    joined = " ".join(
        mx_records
    ).lower()

    if (
        "amazonses" in joined
        or "amazonaws" in joined
    ):
        return "AWS_SES"

    if (
        "google" in joined
        or "gmail" in joined
    ):
        return "GOOGLE_WORKSPACE"

    if (
        "outlook" in joined
        or "microsoft" in joined
    ):
        return "MICROSOFT_365"

    if "zoho" in joined:
        return "ZOHO"

    if "yandex" in joined:
        return "YANDEX"

    return "OTHER"


#################################################
# NS PROVIDER DETECTION
#################################################

def detect_ns_provider(ns_records):

    if not ns_records:
        return None

    joined = " ".join(
        ns_records
    ).lower()

    if "awsdns" in joined:
        return "AWS_ROUTE53"

    if "googledomains" in joined:
        return "GOOGLE_DOMAINS"

    if "azure" in joined:
        return "AZURE_DNS"

    if "cloudflare" in joined:
        return "CLOUDFLARE"

    return None


#################################################
# MULTI IP
#################################################

def resolve_all_ips(domain):

    ips = set()

    try:

        info = socket.getaddrinfo(
            domain,
            None
        )

        for item in info:

            ip = item[4][0]

            ips.add(ip)

    except:
        pass

    return list(ips)


#################################################
# ASN
#################################################

def lookup_asn_single(ip):

    try:

        rdap = (
            IPWhois(ip)
            .lookup_rdap()
        )

        return {

            "asn":
                rdap.get("asn"),

            "asn_description":
                rdap.get(
                    "asn_description"
                )
        }

    except:

        return {}


def lookup_asn(ips):

    if isinstance(ips, str):
        ips = [ips]

    for ip in ips:

        result = lookup_asn_single(ip)

        if result:
            return result

    return {}


#################################################
# TLS
#################################################

def tls_profile(domain):

    result = {}

    try:

        context = (
            ssl.create_default_context()
        )

        with context.wrap_socket(
            socket.socket(),
            server_hostname=domain
        ) as sock:

            sock.settimeout(10)

            sock.connect(
                (domain, 443)
            )

            cert = (
                sock.getpeercert()
            )

            cert_bin = (
                sock.getpeercert(
                    binary_form=True
                )
            )

        result["sha256"] = hashlib.sha256(
            cert_bin
        ).hexdigest()

        result["issuer"] = cert.get(
            "issuer"
        )

        result["subject"] = cert.get(
            "subject"
        )

        result["expiry"] = cert.get(
            "notAfter"
        )

        result["san_domains"] = [

            value

            for _, value in cert.get(
                "subjectAltName",
                []
            )
        ]

        result["wildcard_cert"] = any(

            x.startswith("*.")

            for x in result[
                "san_domains"
            ]
        )

    except Exception as e:

        result["error"] = str(e)

    return result


#################################################
# LEGITIMATE SIGNALS
#################################################

def compute_legitimate_signals(
    tld_info,
    mx_analysis,
    mail_provider,
    txt_analysis,
    cloud_provider,
    ns_provider
):

    tld = tld_info.get("tld", "")

    official_tld = (
        tld in OFFICIAL_TLDS
    )

    business_mail = (
        mx_analysis.get("has_mx", False)
        and mail_provider
        in {
            "AWS_SES",
            "GOOGLE_WORKSPACE",
            "MICROSOFT_365"
        }
    )

    google_verified = (
        txt_analysis.get(
            "google_verification",
            False
        )
    )

    spf_ok = (
        txt_analysis.get(
            "spf_configured",
            False
        )
    )

    major_cloud = (
        cloud_provider is not None
    )

    enterprise_ns = (
        ns_provider is not None
        and ns_provider != "CLOUDFLARE"
    )

    return {

        "official_tld":
            official_tld,

        "business_mail":
            business_mail,

        "google_verification":
            google_verified,

        "spf_configured":
            spf_ok,

        "major_cloud_provider":
            major_cloud,

        "enterprise_dns":
            enterprise_ns,

        "total_signals":
            sum([
                official_tld,
                business_mail,
                google_verified,
                spf_ok,
                major_cloud,
                enterprise_ns
            ])
    }


#################################################
# RISK SCORE (suspicious signals only)
#################################################

def compute_risk_score(e):

    score = 0

    age = e.get(
        "domain_age_days"
    )

    if age is not None and age < 180:
        score += 20

    if e.get(
        "is_whois_privacy_active"
    ):
        score += 10

    if e.get(
        "cloudflare_detected"
    ):
        score += 5

    if not e["mx_analysis"]["has_mx"]:
        score += 10

    if e["tld_info"]["risk"] == "HIGH":
        score += 20

    elif e["tld_info"]["risk"] == "MEDIUM":
        score += 10

    if e.get("redirect_info", {}).get(
        "domain_hopping"
    ):
        score += 25

    if e.get("suspicious_hosting"):
        score += 10

    return min(score, 100)


#################################################
# LEGITIMACY SCORE (legitimate signals only)
#################################################

def compute_legitimacy_score(ls, e):

    score = 0

    if ls.get("official_tld"):
        score += 15

    if ls.get("business_mail"):
        score += 20

    if ls.get("google_verification"):
        score += 10

    if ls.get("spf_configured"):
        score += 10

    if ls.get("major_cloud_provider"):
        score += 15

    if ls.get("enterprise_dns"):
        score += 10

    # Domain age bonus
    age = e.get("domain_age_days")

    if age is not None and age > 365:
        score += 10

    elif age is not None and age > 730:
        score += 20

    return min(score, 100)


#################################################
# MAIN COLLECTOR
#################################################

def collect_step1_evidence(
        domain,
        url):

    whois_info = whois_profile(
        domain
    )

    dns_info = dns_profile(
        domain
    )

    redirects = track_redirects(
        url
    )

    redirect_info = (
        redirect_intelligence(
            redirects
        )
    )

    ips = resolve_all_ips(
        domain
    )

    asn_info = lookup_asn(ips)

    tls_info = tls_profile(
        domain
    )

    # --- New: enriched analysis ---

    asn_desc = asn_info.get(
        "asn_description", ""
    )

    cloud_provider = detect_cloud_provider(
        asn_desc
    )

    suspicious_host = is_suspicious_hosting(
        asn_desc
    )

    txt_analysis = analyze_txt_records(
        dns_info["TXT"]
    )

    mail_provider = classify_mail_provider(
        dns_info["MX"]
    )

    mx_info = analyze_mx(
        dns_info["MX"]
    )

    ns_provider = detect_ns_provider(
        dns_info["NS"]
    )

    tld_info = tld_risk(domain)

    legit_signals = (
        compute_legitimate_signals(
            tld_info,
            mx_info,
            mail_provider,
            txt_analysis,
            cloud_provider,
            ns_provider
        )
    )

    evidence = {

        "domain_age_days":
            whois_info.get(
                "domain_age_days"
            ),

        "creation_date":
            whois_info.get(
                "creation_date"
            ),

        "registrar":
            whois_info.get(
                "registrar"
            ),

        "registrar_risk":
            whois_info.get(
                "registrar_risk"
            ),

        "is_whois_privacy_active":
            whois_info.get(
                "privacy_enabled"
            ),

        "tld_info":
            tld_info,

        "redirect_history":
            redirects,

        "redirect_info":
            redirect_info,

        "dns_records":
            dns_info,

        "cloudflare_detected":
            any(
                "cloudflare"
                in ns.lower()
                for ns in dns_info["NS"]
            ),

        "cdn_providers":
            detect_cdn(
                dns_info["NS"]
            ),

        "http_headers":
            http_fingerprint(
                url
            ),

        "mx_analysis":
            mx_info,

        "mail_provider":
            mail_provider,

        "txt_analysis":
            txt_analysis,

        "cloud_provider":
            cloud_provider,

        "ns_provider":
            ns_provider,

        "suspicious_hosting":
            suspicious_host,

        "resolved_ips":
            ips,

        "asn_info":
            asn_info,

        "tls_info":
            tls_info,

        "legitimate_signals":
            legit_signals
    }

    evidence["risk_score"] = (
        compute_risk_score(
            evidence,
            legit_signals
        )
    )

    return evidence