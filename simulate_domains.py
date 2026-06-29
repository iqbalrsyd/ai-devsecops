#!/usr/bin/env python3
"""
Simulasi perbandingan hasil pipeline .yml untuk 7 domain.
Membandingkan: SAST ruleset, domain-specific job, skip rules,
severity elevation, dan header YAML.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ai-service"))

from app.agents.scan_directives import build_scan_directives
from app.agents.domain_priority import DOMAIN_PRIORITY_RULES

DOMAINS = ["e-commerce", "fintech", "healthcare", "education", "blog", "iot", "general"]

DOMAIN_LABELS = {
    "e-commerce": "E-Commerce",
    "fintech": "Fintech (Ledger)",
    "healthcare": "Healthcare",
    "education": "Education",
    "blog": "Blog / CMS",
    "iot": "IoT / Embedded",
    "general": "General (fallback)",
}

DOMAIN_JOBS_MAP = {
    "e-commerce": "pci-dss",
    "fintech": "ledger-check",
    "healthcare": "hipaa",
    "blog": "csp-headers",
    "iot": "mqtt-security",
    "education": None,
    "general": None,
}

DOMAIN_COMPLIANCE = {
    "e-commerce": "PCI DSS v4.0",
    "fintech": "PCI DSS, SOC2",
    "healthcare": "HIPAA",
    "blog": "OWASP Top 10",
    "iot": "OWASP IoT Top 10",
    "education": "OWASP Top 10",
    "general": "OWASP Top 10",
}

print("=" * 100)
print("  SIMULASI PERBANDINGAN GENERATED PIPELINE .yml UNTUK 7 DOMAIN")
print("  (Asumsi: same architecture = monolithic Node.js + Dockerfile)")
print("=" * 100)
print()
print("Arsitektur di-set sama semua: monolithic, Node.js, ada Dockerfile")
print("Yang berbeda hanya domain context-aware-nya saja.")
print()

# ─── Bagian 1: SAST Ruleset ───
print("─" * 100)
print("  BAGIAN 1: SAST RULESET (Semgrep --config)")
print("─" * 100)
print()

baseline_rules = [
    "p/owasp-top-ten",
    "p/javascript",
    "p/nodejs",
    "p/expressjs",
    "p/sql-injection",
    "p/secrets",
    "p/dockerfile",
]
general_api = "/src/.semgrep/owasp-api.yml"

print(f"BASELINE (selalu ada, 7 registry rules + 1 general-api):")
for r in baseline_rules:
    print(f"  --config={r}")
print(f"  --config={general_api}")
print()

for domain in DOMAINS:
    scan_d = build_scan_directives(detected_domain=domain, arch_type="monolithic")
    domain_rules = [
        r for r in scan_d["sast_ruleset"]
        if r.startswith("/src/.semgrep/") and r != general_api
    ]
    print(f"  [{DOMAIN_LABELS[domain]:20s}] tambahan: {domain_rules if domain_rules else '(none)'}")

print()

# ─── Bagian 2: SAST Skip Rules ───
print("─" * 100)
print("  BAGIAN 2: SAST SKIP RULES (ruled_ids yang di-skip)")
print("─" * 100)
print()

for domain in DOMAINS:
    scan_d = build_scan_directives(detected_domain=domain, arch_type="monolithic")
    skip = scan_d["sast_skip_rules"]
    arch_skip = ["kubernetes", "service-mesh", "istio"]  # karena monolithic
    domain_only = [s for s in skip if s not in ["experimental", "audit", "kubernetes", "service-mesh", "istio"]]
    
    skip_str = ", ".join(skip) if skip else "(none)"
    domain_skip_str = ", ".join(domain_only) if domain_only else "(none)"
    print(f"  [{DOMAIN_LABELS[domain]:20s}] full skip: {skip_str}")
    print(f"  {'':22s}  domain-only: {domain_skip_str}")

print()

# ─── Bagian 3: Job Pipeline ───
print("─" * 100)
print("  BAGIAN 3: JOB PIPELINE (urutan job di .yml)")
print("─" * 100)
print()

CORE_JOBS = ["lint", "test", "sast", "secret-scan", "dependency-scan", "container-scan"]

for domain in DOMAINS:
    scan_d = build_scan_directives(detected_domain=domain, arch_type="monolithic")
    skip_jobs = scan_d["domain_skip_jobs"]
    domain_job = DOMAIN_JOBS_MAP[domain]
    
    jobs = [j for j in CORE_JOBS if j not in skip_jobs]
    if domain_job:
        # domain-specific job ditaruh setelah dependency-scan atau di akhir
        if "dependency-scan" in jobs:
            idx = jobs.index("dependency-scan")
            jobs.insert(idx + 1, domain_job)
        else:
            jobs.append(domain_job)
    
    job_count = len(jobs)
    jobs_str = " → ".join(jobs)
    print(f"  [{DOMAIN_LABELS[domain]:20s}] ({job_count} jobs)  {jobs_str}")

print()

# ─── Bagian 4: Domain-Specific Job Detail ───
print("─" * 100)
print("  BAGIAN 4: JOB SPESIFIK DOMAIN (konten)")
print("─" * 100)
print()

JOB_CONTENT_MAP = {
    "pci-dss": (
        "pci-dss",
        [
            "Scan for hardcoded PAN/CVV (regex VISA/MC/Amex)",
            "Validate .env not in git history",
            "Validate secure payment dependencies",
            "Generate SARIF → upload-sarif + artifact",
        ],
    ),
    "ledger-check": (
        "ledger-check",
        [
            "Scan for non-atomic balance updates (race condition)",
            "Check for missing idempotency keys on transfer endpoints",
            "Generate SARIF → upload-sarif + artifact",
        ],
    ),
    "hipaa": (
        "hipaa",
        [
            "Scan for PHI patterns in source (patient ID, MRN)",
            "Check for weak crypto algorithms (md5/sha1)",
            "Check audit logging presence",
            "Generate SARIF → upload-sarif + artifact",
        ],
    ),
    "csp-headers": (
        "csp-headers",
        [
            "Static check for security header middleware (helmet/Talisman)",
            "Check X-Frame-Options configuration",
            "Check HSTS configuration",
            "Generate SARIF → upload-sarif + artifact",
        ],
    ),
    "mqtt-security": (
        "mqtt-security",
        [
            "Scan for cleartext MQTT (mqtt://) broker URLs",
            "Check for default credentials (admin/admin, root/user, etc.)",
            "Check for TLS verification disabled (CERT_NONE, rejectUnauthorized=false)",
            "Generate SARIF → upload-sarif + artifact",
        ],
    ),
}

for domain in DOMAINS:
    job_name = DOMAIN_JOBS_MAP[domain]
    if job_name and job_name in JOB_CONTENT_MAP:
        name, steps = JOB_CONTENT_MAP[job_name]
        print(f"  [{DOMAIN_LABELS[domain]:20s}] JOB: {name}")
        for i, step in enumerate(steps, 1):
            print(f"  {'':22s}  Step {i}: {step}")
        print(f"  {'':22s}  Compliance: {DOMAIN_COMPLIANCE[domain]}")
    else:
        print(f"  [{DOMAIN_LABELS[domain]:20s}] (no domain-specific job)")
        print(f"  {'':22s}  Compliance: {DOMAIN_COMPLIANCE[domain]}")
    print()

# ─── Bagian 5: Severity Elevation (Priority Rules) ───
print("─" * 100)
print("  BAGIAN 5: SEVERITY ELEVATION KEYWORDS (via domain_priority.py)")
print("  (Keyword di findings → severity dinaikkan ke CRITICAL/HIGH)")
print("─" * 100)
print()

for domain in DOMAINS:
    rules = DOMAIN_PRIORITY_RULES.get(domain, DOMAIN_PRIORITY_RULES["general"])
    critical_kw = rules.get("critical_keywords", [])
    high_kw = rules.get("high_keywords", [])
    file_patterns = rules.get("file_patterns", [])
    
    print(f"  [{DOMAIN_LABELS[domain]:20s}]")
    if critical_kw:
        kw_str = ", ".join(critical_kw[:6])
        if len(critical_kw) > 6:
            kw_str += f", ... (+{len(critical_kw)-6} more)"
        print(f"  {'':22s}  → CRITICAL: {kw_str}")
    else:
        print(f"  {'':22s}  → CRITICAL: (none)")
    if high_kw:
        kw_str = ", ".join(high_kw[:6])
        if len(high_kw) > 6:
            kw_str += f", ... (+{len(high_kw)-6} more)"
        print(f"  {'':22s}  → HIGH:     {kw_str}")
    else:
        print(f"  {'':22s}  → HIGH:     (none)")
    if file_patterns:
        fp_str = ", ".join(file_patterns[:6])
        if len(file_patterns) > 6:
            fp_str += f", ... (+{len(file_patterns)-6} more)"
        print(f"  {'':22s}  → FILE:     {fp_str}")
    print()

# ─── Bagian 6: YAML Header ───
print("─" * 100)
print("  BAGIAN 6: YAML HEADER COMMENT (domain context)")
print("─" * 100)
print()

for domain in DOMAINS:
    from app.agents.nodes.domain_detection_node import DOMAIN_LIBRARY_INDICATORS
    threats = DOMAIN_LIBRARY_INDICATORS.get(domain, {}).get("threats", []) if domain != "general" else []
    
    print(f"  [{DOMAIN_LABELS[domain]:20s}]")
    print(f'  {"":22s}  # Domain: {domain} (confidence: 0.85)')
    print(f'  {"":22s}  # Architecture: monolithic')
    if threats:
        threat_str = "; ".join(threats[:3])
        print(f'  {"":22s}  # Priority threats: {threat_str}')
    else:
        print(f'  {"":22s}  # Priority threats: none specific (no domain detected)')
    print()

# ─── Bagian 7: Ringkasan Matriks Perbandingan ───
print("═" * 100)
print("  RINGKASAN MATRIKS: WHAT'S DIFFERENT ACROSS DOMAINS")
print("═" * 100)
print()

# Build comparison table
headers = ["Dimension", "e-commerce", "fintech", "healthcare", "education", "blog", "iot", "general"]
col_widths = [22, 16, 16, 16, 16, 16, 16, 16]

row_sep = "  +" + "+".join("-" * (w + 2) for w in col_widths[1:])
row_fmt = "  | {:<" + str(col_widths[0]) + "} |" + "|".join(" {:<" + str(w) + "}" for w in col_widths[1:]) + " |"

# count_jobs
def count_jobs(domain):
    scan_d = build_scan_directives(detected_domain=domain, arch_type="monolithic")
    skip_jobs = scan_d["domain_skip_jobs"]
    domain_job = DOMAIN_JOBS_MAP[domain]
    jobs = [j for j in CORE_JOBS if j not in skip_jobs]
    if domain_job:
        jobs.append(domain_job)
    return len(jobs)
def count_rules(domain):
    scan_d = build_scan_directives(detected_domain=domain, arch_type="monolithic")
    return len(scan_d["sast_ruleset"])
def count_skip(domain):
    scan_d = build_scan_directives(detected_domain=domain, arch_type="monolithic")
    return len(scan_d["sast_skip_rules"])
def count_critical(domain):
    return len(DOMAIN_PRIORITY_RULES.get(domain, {}).get("critical_keywords", []))
def count_high(domain):
    return len(DOMAIN_PRIORITY_RULES.get(domain, {}).get("high_keywords", []))

print(row_fmt.format(*headers))
print(row_sep)

def row(label, fn):
    return row_fmt.format(label, *[str(fn(d)) for d in DOMAINS])

print(row("Job Count", count_jobs))
print(row("SAST Total Rules", count_rules))
print(row("SAST Skip Rules", count_skip))
print(row("CRITICAL Keywords", count_critical))
print(row("HIGH Keywords", count_high))
print(row("Domain-Specific Job", lambda d: DOMAIN_JOBS_MAP[d] or "(none)"))
