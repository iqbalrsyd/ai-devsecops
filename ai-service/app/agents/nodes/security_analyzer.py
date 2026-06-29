import json
import re

from app.agents.pipeline_state import PipelineEngineerState
from app.agents.pipeline_schemas import SecurityFinding
from app.services.llm_service import get_llm
from app.services.github_service import get_workflow_logs

SECURITY_ANALYSIS_PROMPT = """You are a DevSecOps security analyst analyzing scanner output from a CI/CD pipeline.

Below is the raw scanner data and workflow logs from a GitHub Actions run. Parse the findings and return a JSON list of security issues.

Data:
{data}

For each issue found, return a JSON list of findings with these fields:
- type: type of issue (hardcoded_secret, sql_injection, xss, command_injection, dependency_vulnerability, insecure_config, etc.)
- severity: critical/high/medium/low
- scanner: semgrep/trivy/gitleaks/dep-check/ai
- file: affected file path
- line: line number (integer or null)
- code_snippet: relevant code snippet
- package_name: if dependency issue, the package name
- installed_version: if dependency issue, the installed version
- fixed_version: if dependency issue, the fixed version
- cve: CVE identifier if applicable
- cwe: CWE identifier if applicable (e.g. CWE-79)
- owasp: OWASP category if applicable (e.g. A1: Injection)
- explanation: clear explanation of the security issue
- impact: business/security impact
- recommendation: how to fix it

Return ONLY valid JSON array. If no issues found, return [].
"""


def _parse_scanner_output(logs_text: str) -> dict:
    parsed = {"raw_logs": logs_text[:10000], "findings": []}

    sarif_patterns = ['"sarif"', '"results"', '"ruleId"']
    trivy_patterns = ['"Vulnerabilities"', '"Target"', '"PkgName"']
    gitleaks_patterns = ['"Description"', '"Match"', '"Secret"']
    depcheck_patterns = ['"vulnerabilities"', '"evidenceCollected"']

    text_lower = logs_text.lower()

    if any(p.lower() in text_lower for p in sarif_patterns):
        parsed["has_semgrep"] = True
    if any(p.lower() in text_lower for p in trivy_patterns):
        parsed["has_trivy"] = True
    if any(p.lower() in text_lower for p in gitleaks_patterns):
        parsed["has_gitleaks"] = True
    if any(p.lower() in text_lower for p in depcheck_patterns):
        parsed["has_depcheck"] = True

    for line in logs_text.split("\n"):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                parsed_data = json.loads(line)
                if isinstance(parsed_data, dict):
                    if "results" in parsed_data:
                        parsed["semgrep_results"] = parsed_data
                    elif "Vulnerabilities" in parsed_data:
                        parsed["trivy_results"] = parsed_data
                    elif "Description" in parsed_data and "Match" in parsed_data:
                        parsed["gitleaks_results"] = parsed_data
                elif isinstance(parsed_data, list):
                    parsed["json_list"] = parsed_data
            except (json.JSONDecodeError, ValueError):
                pass

    return parsed


def security_analyzer_node(state: PipelineEngineerState) -> PipelineEngineerState:
    raw_data = state.get("scan_results", {}) or {}
    findings_raw = state.get("findings", [])
    logs = state.get("workflow_logs", [])
    repo = state.get("repository_full_name", "")
    run_id = state.get("workflow_run_id")
    github_token = state.get("github_token", "")

    if run_id and repo:
        try:
            log_text = get_workflow_logs(repo, run_id, github_token)
            if log_text:
                scanner_data = _parse_scanner_output(log_text)
                raw_data["scanner_output"] = scanner_data
                state["scan_results"] = raw_data
        except Exception:
            pass

    logs_text = "\n".join(
        f"[{l.get('job','')}/{l.get('step','')}] {l.get('status','')} {l.get('conclusion','')}"
        for l in (logs or [])
    )

    data = {"logs": logs_text[:5000], "scanner_data": str(raw_data.get("scanner_output", {}))[:5000]}

    prompt = SECURITY_ANALYSIS_PROMPT.format(data=str(data)[:10000])
    llm = get_llm()

    try:
        response = llm.invoke(prompt)
        from app.agents.llm_response_parser import parse_llm_json_array
        parsed_list = parse_llm_json_array(response.content)
        if parsed_list is None:
            raise ValueError(f"Invalid JSON after cleanup: {response.content[:200]}...")
        if isinstance(parsed_list, list):
            validated = []
            for item in parsed_list:
                try:
                    sf = SecurityFinding(**item)
                    validated.append(sf.model_dump())
                except Exception:
                    validated.append(item)
            # Bab 5.13.3: tag every finding with CVSS via the 3-tier
            # lookup in cvss_mapper (RULE_CVSS_MAP → TYPE_CVSS_FALLBACK
            # → SEVERITY_DEFAULT) so the FE has a numeric score,
            # vector, and severity band per finding.
            try:
                from app.agents.cvss_mapper import score_findings
                score_findings(validated)
            except Exception:
                pass
            state["findings"] = validated
        else:
            state["findings"] = findings_raw
    except Exception as e:
        state["errors"].append(f"Security analysis parsing failed: {e}")
        state["findings"] = findings_raw

    # Bab 5.13.3: recompute the 3 dashboard scores from the FINAL
    # findings list (which may include the SARIF-derived alerts).
    # `risk_score` is "higher = safer" so the formula is:
    #     risk_score = 100 - (avg(CVSS) / 10) * 100
    # `compliance_score` is the percentage of applicable security
    # coverages that resolved to at least one finding, capped at 100.
    # `security_coverage_score` is the percentage of the 15 coverages
    # that the AI agent marked applicable.
    try:
        from app.agents.cvss_mapper import score_findings
        score_findings(state["findings"])
        cvss_scores = [
            float(f.get("cvss_score") or 0.0)
            for f in (state["findings"] or [])
            if isinstance(f.get("cvss_score"), (int, float))
        ]
        if cvss_scores:
            avg_cvss = sum(cvss_scores) / len(cvss_scores)
            state["risk_score"] = round(max(0.0, 100.0 - (avg_cvss / 10.0) * 100.0), 1)
        elif state["findings"]:
            # No CVSS available — keep whatever was set previously,
            # defaulting to 80 ("medium-low" risk) so the dashboard
            # does not pretend the pipeline is risk-free.
            state.setdefault("risk_score", 80.0)
        else:
            state["risk_score"] = 100.0
    except Exception:
        pass

    try:
        coverages = state.get("security_coverages") or []
        applicable = sum(1 for c in coverages if c.get("applicable"))
        state["security_coverage_score"] = round(
            (applicable / max(1, len(coverages))) * 100.0, 1
        ) if coverages else 0.0
    except Exception:
        pass

    try:
        # compliance_score: every distinct finding carries at least one
        # applicable security coverage. The score is the share of
        # applicable coverages that have at least one finding.
        coverages = state.get("security_coverages") or []
        applicable_ids = {c.get("id") for c in coverages if c.get("applicable")}
        covered_ids = {
            (f.get("security_coverage") or "")
            for f in (state["findings"] or [])
        }
        if applicable_ids:
            matched = len(applicable_ids & covered_ids)
            state["compliance_score"] = round(
                (matched / len(applicable_ids)) * 100.0, 1
            )
        else:
            state["compliance_score"] = 0.0
    except Exception:
        pass

    return state


def _safe_json_loads(text: str):
    """Parse JSON with cleanup for common LLM issues."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r',\s*([\]}])', r'\1', text)
    text = re.sub(r'(?<!:)\s*//.*', '', text)
    text = re.sub(r"(?<=[{,]\s)'([^']*)'(?=\s*[:,\]}])", r'"\1"', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return None