from step1 import *


def build_evidence_buffer(
        domain,
        url
):

    whois_info = whois_profile(domain)

    dns_info = dns_profile(domain)

    redirects = track_redirects(url)

    redirect_info = (
        redirect_intelligence(
            redirects
        )
    )

    ips = resolve_all_ips(domain)

    asn_info = lookup_asn(ips)

    # --- Enriched analysis ---

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

    cdn_list = detect_cdn(
        dns_info["NS"]
    )

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

        "detected_ns":
            dns_info["NS"],

        "cloudflare_detected":
            "cloudflare" in cdn_list,

        "cdn_providers":
            cdn_list,

        "http_headers":
            http_fingerprint(url),

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

        "resolved_ip":
            ips,

        "asn_info":
            asn_info,

        "legitimate_signals":
            legit_signals
    }

    evidence["risk_score"] = (
        compute_risk_score(
            evidence
        )
    )

    evidence["legitimacy_score"] = (
        compute_legitimacy_score(
            legit_signals,
            evidence
        )
    )

    return evidence