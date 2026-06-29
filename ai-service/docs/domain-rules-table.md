# Domain Rules Table — Source of Truth untuk Skripsi Bab 4 §4.4

> **Regenerate manual** kalau ada perubahan di `scan_directives.py` atau `llm_generation_config.py`.
> Selaras dengan `app/agents/semgrep_rules/index.yml` (Tier 1) + `app/agents/scan_directives.py` (skip rules + arch) + `app/agents/semgrep_rules/llm_generation_config.py` (Tier 3).
>
> **Desain final (keputusan user)**: HANYA 2 tier. **TIDAK ADA sub-type payment processor rules**. Tier 1 (statis) + Tier 3 (LLM-generated, opt-in) digabung jadi 1 file `.yml` per pipeline run.

## Tabel Perbedaan Per Domain

| Domain      | Tier 1: Static `.yml` (Selalu Aktif)        | Tier 3: LLM-Generated Scope (Opt-In)                                  | File Hasil di `.semgrep/`                       | Domain Jobs   | Skip Jobs                                                                |
|-------------|----------------------------------------------|-----------------------------------------------------------------------|------------------------------------------------|---------------|--------------------------------------------------------------------------|
| e-commerce  | `ecommerce.yml`, `pci-dss.yml`               | ON — payment, BOLA cart, price tampering, webhook forgery             | `e-commerce-combined-<hash>.yml`               | `pci-dss`     | —                                                                        |
| fintech     | `ecommerce.yml`, `fintech-ledger.yml`        | ON — ledger integrity, KYC bypass, replay attack, transfer tampering  | `fintech-combined-<hash>.yml`                  | `ledger-check`| —                                                                        |
| healthcare  | `hipaa.yml`                                  | ON — PHI exposure, weak auth medical records, audit log gaps          | `healthcare-combined-<hash>.yml`                | `hipaa`       | `command-injection`                                                      |
| blog        | `blog-csp.yml`                               | ON — XSS in comment, file upload bypass, content injection via markdown| `blog-combined-<hash>.yml`                      | `csp-headers` | `container-scan`, `idor`, `ssrf`, `jwt`, `rate-limiting`                 |
| iot         | `iot-mqtt.yml`                               | ON — device auth bypass, MQTT no-encrypt, firmware tampering, default creds | `iot-combined-<hash>.yml`                  | `mqtt-security`| —                                                                       |
| education   | — (kosong)                                   | ON — student data leak, cheating bypass, grade tampering, weak access ctrl | `education-combined-<hash>.yml`            | —             | `ssrf`, `rate-limiting`                                                  |
| general     | `owasp-api.yml` (sama dengan baseline)       | **OFF** — tidak di-generate untuk domain general                      | `owasp-api.yml` saja (Tier 1)                  | —             | `pci-dss`, `hipaa`, `ledger-check`, `csp-headers`, `mqtt-security`       |

## Tier 3 — Aturan Wajib (Batasan)

1. **Scope domain**: hanya 6 domain utama. `general` dikecualikan — kalau tidak ada sinyal domain, jangan generate rule baru.
2. **Confidence threshold**: `MIN_LLM_CONFIDENCE = 0.7`. Rule di bawah threshold di-drop, dicatat di state.
3. **Max rules per domain**: `MAX_RULES_PER_DOMAIN = 5`.
4. **Severity default**: `WARNING` (bukan `ERROR`) di first generation.
5. **ID prefix wajib**: `{domain}-custom-{slug}` — contoh: `ecommerce-custom-price-tampering`.
6. **Filename pattern**: `<domain>-combined-<8-char-hash>.yml` — Tier 1 + Tier 3 digabung jadi 1 file.
7. **Cache key**: `SHA-256(domain, domain_threats, primary_language, frameworks)`.
8. **Validasi**: `semgrep --validate` di workflow CI step `Validate custom Semgrep rules` (continue-on-error: true).
9. **Feature flag**: `ENABLE_LLM_GENERATED_RULES=false` (default). Set `true` untuk opt-in.
10. **Storage**: file di-commit ke `.semgrep/<file>.yml` di repo target via PR (sama dengan Tier 1).

## Tier 1 — Baseline (Selalu Aktif untuk Semua Repo)

**Layer 1: Always-On Baseline** (di `scan_directives.py:_BASELINE_REGISTRY_RULES`)
- `p/owasp-top-ten`
- `p/javascript`
- `p/nodejs`
- `p/expressjs`
- `p/sql-injection`
- `p/secrets`
- `p/dockerfile`

**Layer 1: Custom baseline** (di `scan_directives.py:_GENERAL_API_RULES`)
- `owasp-api.yml` (OWASP API Security Top 10 2023)

**Layer 1: Skip rules** (di `scan_directives.py:_BASELINE_SKIP_RULES`)
- `experimental`
- `audit`

**Layer 3 (arch-specific skip)** (di `scan_directives.py`)
- `arch_type == "monolithic"`: tambah skip `kubernetes`, `service-mesh`, `istio`

## Catatan

- Tabel ini untuk **dokumentasi skripsi** (Bab 4 §4.4 atau lampiran).
- Source of truth kode: `app/agents/scan_directives.py` (Tier 1), `app/agents/semgrep_rules/llm_generation_config.py` (Tier 3).
- Sub-type payment processor rules **TIDAK dipakai** — keputusan desain user, bukan per-tier config.
