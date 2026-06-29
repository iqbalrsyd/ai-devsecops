from app.agents.pipeline_state import PipelineEngineerState


OWASP_CONTROLS = [
    {"control_id": "CICD-SAST-01", "control_name": "SAST scan present", "check": "sast"},
    {"control_id": "CICD-DEP-01", "control_name": "Dependency scan present", "check": "dependency-scan"},
    {"control_id": "CICD-SEC-01", "control_name": "Secret scan present", "check": "secret-scan"},
    {"control_id": "CICD-CON-01", "control_name": "Container scan present (if Docker)", "check": "container-scan"},
    {"control_id": "CICD-PIN-01", "control_name": "Actions pinned to SHA", "check": "actions_pinned"},
    {"control_id": "CICD-PRM-01", "control_name": "Minimal permissions", "check": "permissions_minimal"},
    {"control_id": "CICD-CUR-01", "control_name": "Concurrency configured", "check": "concurrency"},
    {"control_id": "CICD-DPL-01", "control_name": "Deploy gated with condition", "check": "deploy_gated"},
]


def compliance_mapper_node(state: PipelineEngineerState) -> PipelineEngineerState:
    findings = state.get("findings", [])
    security = state.get("inferred_security_needs", {}) or {}
    security_reqs = security.get("required_stages", [])
    validation_errors = state.get("validation_errors", [])
    validation_warnings = state.get("validation_warnings", [])

    finding_types = set()
    for f in findings:
        if isinstance(f, dict):
            finding_types.add(f.get("type", ""))
        elif hasattr(f, "type"):
            finding_types.add(f.type)

    mappings = []
    passed_controls = 0
    total_controls = len(OWASP_CONTROLS)

    for control in OWASP_CONTROLS:
        check = control["check"]
        status = "not_applicable"

        if check == "sast":
            status = "passed" if "sast" in security_reqs else "not_applicable"
        elif check == "dependency-scan":
            status = "passed" if "dependency-scan" in security_reqs else "not_applicable"
        elif check == "secret-scan":
            status = "passed" if "secret-scan" in security_reqs else "not_applicable"
        elif check == "container-scan":
            tech = state.get("detected_technologies", {}) or {}
            has_container = tech.get("has_dockerfile", False)
            status = "passed" if has_container and "container_scan" in security_reqs else "not_applicable"
        elif check == "actions_pinned":
            has_pin_errors = any("pinned" in e.lower() or "sha" in e.lower() for e in validation_errors)
            status = "failed" if has_pin_errors else "passed"
        elif check == "permissions_minimal":
            has_perm_warnings = any("permission" in w.lower() for w in validation_warnings)
            status = "failed" if has_perm_warnings else "passed"
        elif check == "concurrency":
            has_conc_warnings = any("concurrency" in w.lower() for w in validation_warnings)
            status = "failed" if has_conc_warnings else "passed"
        elif check == "deploy_gated":
            has_gate_warnings = any("if:" in w.lower() or "condition" in w.lower() for w in validation_warnings)
            status = "failed" if has_gate_warnings else "passed"

        if status == "passed":
            passed_controls += 1

        mappings.append({
            "framework": "OWASP_CICD",
            "control_id": control["control_id"],
            "control_name": control["control_name"],
            "status": status,
            "finding_refs": [],
        })

    compliance_score = round((passed_controls / total_controls) * 100, 1) if total_controls > 0 else 0
    state["compliance_mappings"] = mappings
    state["compliance_score"] = compliance_score

    return state