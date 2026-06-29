# 5. Detailed Logic Flow

## 5.1 Repository Analysis Logic Flow

### Inputs
| Input | Source | Format | Example |
|---|---|---|---|
| Repository URL | User selection / GitHub API | `https://github.com/{owner}/{repo}` | `https://github.com/facebook/react` |
| GitHub Access Token | OAuth / PAT | Bearer token string | `gho_xxxx...` / `ghp_xxxx...` |
| Repository Metadata | GitHub API (`GET /repos/{owner}/{repo}`) | JSON | `{default_branch: "main", language: "TypeScript", size: 45000}` |
| Branch Reference | Config (default: default branch) | String | `"main"` |

### Processes

**Step 1: Clone Repository**
```
FUNCTION clone_repository(repo_url, token, branch):
    1. CONSTRUCT authenticated URL:
       authenticated_url = f"https://{token}@github.com/{repo_url.split('github.com/')[1]}"
    2. CREATE temp directory: /tmp/repos/{uuid4()}/
    3. EXECUTE git clone:
       git clone --depth=1 --single-branch --branch={branch} {authenticated_url} {temp_dir}
    4. IF clone FAILS with auth error:
         RETRY with GitHub App installation token
         IF still failing: FALLBACK to GitHub Tree API (read-only)
    5. RETURN {clone_path: temp_dir, success: bool, fallback_mode: bool}
```

**Step 2: Scan File Tree**
```
FUNCTION scan_file_tree(clone_path):
    1. RECURSIVELY walk directory tree
    2. FOR each file:
       - RECORD: relative_path, file_name, extension, size_bytes
       - SKIP: .git/, node_modules/, __pycache__/, .venv/, vendor/, target/,
               *.pyc, *.class, *.o, *.so, *.dll, binary files > 1MB
    3. BUILD file_manifest list sorted by directory depth
    4. COUNT file extensions → language_distribution map
    5. RETURN {file_manifest, language_distribution, total_files, total_directories}
```

**Step 3: Identify Manifest Files**
```
FUNCTION identify_manifests(file_manifest):
    1. SCAN for known manifest patterns:
       - package.json       → Node.js/JavaScript/TypeScript
       - requirements.txt   → Python (pip)
       - Pipfile/Pipfile.lock → Python (Pipenv)
       - pyproject.toml      → Python (Poetry/Hatch)
       - go.mod              → Go
       - Cargo.toml          → Rust
       - pom.xml             → Java (Maven)
       - build.gradle        → Java/Kotlin (Gradle)
       - build.gradle.kts    → Kotlin DSL (Gradle)
       - Gemfile             → Ruby
       - composer.json       → PHP
       - CMakeLists.txt      → C/C++ (CMake)
       - Makefile            → Generic build
       - Dockerfile          → Docker
       - docker-compose.yml  → Docker Compose
       - .github/workflows/*.yml → Existing CI/CD
       - k8s/**/*.yml        → Kubernetes
       - terraform/**/*.tf   → Terraform
    2. READ contents of each found manifest file
    3. RETURN {manifest_map: {filename: contents}}
```

**Step 4: LLM-Powered Technology Classification**
```
FUNCTION classify_technologies(file_manifest, manifest_map, language_distribution):
    1. CONSTRUCT LLM prompt:
       """
       SYSTEM: You are a software technology detection expert.
       Analyze the repository structure and identify all technologies used.
       
       FILE TREE (truncated to top 200 files):
       {serialized_file_tree}
       
       MANIFEST FILES:
       {serialized_manifests}
       
       FILE EXTENSION DISTRIBUTION:
       {language_distribution}
       
       TASK: Return a JSON object with:
       {{
         "languages": [{{"name": str, "version": str|null, "confidence": 0.0-1.0, "evidence": str}}],
         "frameworks": [{{"name": str, "version": str|null, "confidence": 0.0-1.0, "evidence": str}}],
         "build_tools": [{{"name": str, "confidence": 0.0-1.0, "evidence": str}}],
         "test_frameworks": [{{"name": str, "confidence": 0.0-1.0, "evidence": str}}],
         "deployment_configs": [{{"type": str, "files": [str], "confidence": 0.0-1.0}}]
       }}
       """
    2. CALL OpenRouter LLM with structured_output mode
    3. PARSE JSON response
    4. CROSS-VALIDATE:
       - IF 'Python' detected BUT no requirements.txt/setup.py → Lower confidence by 0.1
       - IF 'Docker' detected BUT no Dockerfile → Flag as anomaly
       - IF no test framework detected BUT test/ directory exists → Add "unknown" with low confidence
    5. RETURN structured technology classification
```

### Decision Rules

| Condition | Action |
|---|---|
| `file_manifest.length > 1000` | Truncate file tree to first 500 files; note truncation in prompt |
| `manifest_map` is empty | Use heuristic mode: language detection by extension only |
| `language_distribution` shows 1 dominant language (>90%) | Skip detailed LLM classification; use heuristic for secondary detection |
| LLM returns `confidence < 0.7` for any technology | Mark as "uncertain"; request user confirmation via UI |
| Repository is a monorepo (multiple build manifests in subdirs) | Branch into per-workspace sub-analysis; merge results |
| Token count for prompt > 8000 | Split into chunks (file tree + manifests + distribution analyzed separately) |

### Outputs

```json
{
  "job_id": "uuid-1234",
  "repository_id": "repo-5678",
  "status": "completed",
  "technologies": {
    "languages": [
      {"name": "TypeScript", "version": "5.4", "confidence": 0.98, "evidence": "tsconfig.json, .tsx files (142 files)"},
      {"name": "JavaScript", "version": null, "confidence": 0.95, "evidence": "package.json engines.node >= 18"}
    ],
    "frameworks": [
      {"name": "React", "version": "18.3", "confidence": 0.97, "evidence": "package.json dependency react@^18.3.1"},
      {"name": "Next.js", "version": "14.2", "confidence": 0.92, "evidence": "next.config.js, package.json next@^14.2.0"}
    ],
    "build_tools": [
      {"name": "npm", "confidence": 0.99, "evidence": "package-lock.json present"},
      {"name": "webpack", "confidence": 0.85, "evidence": "webpack.config.js"}
    ],
    "test_frameworks": [
      {"name": "Jest", "confidence": 0.93, "evidence": "package.json devDependency jest@^29.7.0"},
      {"name": "React Testing Library", "confidence": 0.88, "evidence": "package.json @testing-library/react"}
    ],
    "deployment_configs": [
      {"type": "Docker", "files": ["Dockerfile", "docker-compose.yml"], "confidence": 0.96}
    ]
  },
  "error": null,
  "analysis_duration_ms": 45000
}
```

---

## 5.2 Workflow Generation Logic Flow

### Inputs
| Input | Source | Format |
|---|---|---|
| Technology Classification | Analysis Results (Section 5.1 output) | JSON |
| User Configuration | UI form submission | `{triggers: ["push", "pull_request"], enabled_tools: ["semgrep", "gitleaks", "trivy", "codeql", "dep-review"], target_branch: "main"}` |
| Repository Metadata | Database | `{default_branch, visibility, archived}` |
| Existing Workflows | GitHub API / Database | `[{path: ".github/workflows/ci.yml", content: "..."}]` |

### Processes

**Step 1: Build Context for LLM Generation**
```
FUNCTION build_generation_context(technologies, user_config, repo_metadata):
    1. COMPILE technology summary:
       tech_summary = f"""
       Languages: {[t['name'] for t in technologies['languages']]}
       Frameworks: {[t['name'] for t in technologies['frameworks']]}
       Build Tools: {technologies['build_tools']}
       Test Frameworks: {technologies['test_frameworks']}
       Deployment: {technologies['deployment_configs']}
       """
    
    2. BUILD security requirements list from Security Requirement Agent output
    
    3. COMPILE constraints:
       constraints = [
         "All action versions MUST be pinned (e.g., @v4, never @main or @latest)",
         "Secrets MUST use ${{{{ secrets.SECRET_NAME }}}} syntax",
         "Include 'permissions: contents: read' by default",
         "Each job should have a timeout-minutes (max 30)",
         "Use actions/checkout@v4 as the first step in each job",
         f"Target branch: {user_config['target_branch']}",
         f"Enabled security tools: {user_config['enabled_tools']}",
         f"Workflow triggers: {user_config['triggers']}"
       ]
    
    4. RETURN {tech_summary, security_requirements, constraints}
```

**Step 2: Structured LLM Generation**
```
FUNCTION generate_workflow_yaml(context):
    1. LOAD system prompt template (from prompts/workflow_generation.py)
    
    2. CONSTRUCT messages:
       [
         {
           "role": "system",
           "content": """You are a DevSecOps expert generating production-grade 
           GitHub Actions workflow YAML. Generate a COMPLETE workflow that includes:
           - Checkout, Setup, Build, Test stages
           - Security scanning stages (SAST, secret detection, dependency scanning)
           - Docker image scanning (if Docker detected)
           - Deployment (if deployment config detected)
           
           CRITICAL RULES:
           - Output ONLY valid YAML, no markdown fences
           - Pin all action versions
           - Use ${{{{ secrets.* }}}} for all credentials
           - Each job must have runs-on: ubuntu-latest
           - Include concurrency group to prevent parallel runs
           """
         },
         {
           "role": "user",
           "content": f"""
           Technology Stack:
           {context['tech_summary']}
           
           Security Requirements:
           {context['security_requirements']}
           
           Constraints:
           {context['constraints']}
           
           Generate a complete GitHub Actions workflow YAML.
           """
         }
       ]
    
    3. CALL OpenRouter LLM (model: secondary)
       Parameters: temperature=0.2, max_tokens=8192
    
    4. POST-PROCESS LLM output:
       - STRIP markdown fences (```yaml ... ```) if present
       - PARSE with YAML parser to verify syntax
       - FORMAT with consistent 2-space indentation
       - ADD header comment: "# Generated by AI-Powered DevSecOps Agent\n# {timestamp}"
    
    5. GENERATE unique filename: f"devsecops-{tech_slug}-{timestamp}.yml"
    
    6. RETURN {workflow_yaml, filename, generation_metadata}
```

### Decision Rules

| Condition | Action |
|---|---|
| `technologies.languages` is empty | Generate generic workflow with build/test placeholders; warn user |
| Monorepo detected | Generate matrix strategy workflow or separate workflow files per package |
| Dockerfile detected | ADD Trivy image scan + Dockle lint stage |
| Kubernetes manifests detected | ADD Kubesec scan + Trivy config scan stage |
| `user_config.enabled_tools` is empty | Add mandatory minimum: Gitleaks + one SAST tool |
| Multiple languages detected | ADD matrix build strategy (parallel language-specific jobs) |
| Existing `.github/workflows/` has files | Check for conflicts; add warning if workflow name collision |
| `repo_metadata.visibility == "public"` | ADD workflow security hardening (restrict token permissions) |
| Token count approaching limit | SPLIT generation: generate build pipeline first, then security stages, then stitch |

### Outputs

```yaml
# Generated by AI-Powered DevSecOps Agent
# 2026-06-08T10:30:00Z

name: DevSecOps Pipeline (React/Next.js + Docker)

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  NODE_VERSION: '20'

jobs:
  build-and-test:
    name: Build & Test
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
      - run: npm ci
      - run: npm run build
      - run: npm test -- --coverage

  semgrep-sast:
    name: Semgrep SAST Scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    container:
      image: returntocorp/semgrep
    steps:
      - uses: actions/checkout@v4
      - run: semgrep ci --sarif --output=semgrep.sarif
        env:
          SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: semgrep.sarif

  gitleaks-secret-scan:
    name: Gitleaks Secret Detection
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}

  trivy-dependency-scan:
    name: Trivy Dependency Scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-deps.sarif'
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-deps.sarif

  trivy-docker-scan:
    name: Trivy Docker Image Scan
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t app:${{ github.sha }} .
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: app:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-image.sarif'
          severity: 'CRITICAL,HIGH'
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-image.sarif

  dependency-review:
    name: Dependency Review
    runs-on: ubuntu-latest
    timeout-minutes: 5
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4

  codeql-analysis:
    name: CodeQL Analysis
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: ['javascript-typescript']
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3
```

---

## 5.3 Workflow Validation Logic Flow

### Inputs
| Input | Source | Format |
|---|---|---|
| Workflow YAML | Generator or Repair Agent output | String (YAML) |
| GitHub Actions Schema | Embedded JSON Schema file | JSON |
| Security Policy Rules | Database config | `[{rule_id, rule_name, check_type, severity, pattern}]` |
| Technology Context | Analysis Results | JSON |

### Processes

**Step 1: Syntax Validation**
```
FUNCTION validate_syntax(yaml_string):
    1. TRY:
         parsed = yaml.safe_load(yaml_string)  # Using ruamel.yaml for strict mode
    2. CATCH YAMLError as e:
         RETURN {{
           valid: false,
           errors: [{{
             type: "SYNTAX_ERROR",
             line: e.problem_mark.line + 1,
             column: e.problem_mark.column + 1,
             message: e.problem,
             fixable: true
           }}]
         }}
    3. IF parsed is None or not isinstance(parsed, dict):
         RETURN {{valid: false, errors: [{{type: "EMPTY_YAML", message: "YAML document is empty or not a mapping"}}]}}
    4. RETURN {parsed, valid: true, errors: []}
```

**Step 2: Schema Validation**
```
FUNCTION validate_schema(parsed_yaml):
    1. LOAD GitHub Actions JSON Schema (github-workflow-schema.json)
    2. VALIDATE parsed_yaml against schema using jsonschema library:
       validator = jsonschema.Draft202012Validator(schema)
       errors = list(validator.iter_errors(parsed_yaml))
    3. FORMAT errors:
       schema_errors = [
         {
           "type": "SCHEMA_ERROR",
           "path": " → ".join(error.absolute_path),
           "message": error.message,
           "fixable": error.validator in ["required", "type", "pattern"]
         }
         for error in errors
       ]
    4. RETURN {{valid: len(schema_errors) == 0, errors: schema_errors}}
```

**Step 3: Security Policy Validation**
```
FUNCTION validate_security_policy(parsed_yaml, technology_context, policy_rules):
    security_errors = []
    
    # Rule 1: Required security tools presence
    FOR tool in technology_context.security_requirements.tools:
        IF tool not found in parsed_yaml.jobs:
            security_errors.append({
                "type": "MISSING_SECURITY_TOOL",
                "tool": tool,
                "severity": "HIGH",
                "message": f"Required security tool '{tool}' not found in workflow jobs",
                "fixable": true
            })
    
    # Rule 2: Action version pinning
    FOR job in parsed_yaml.jobs:
        FOR step in job.steps:
            IF step.uses is defined:
                action_ref = extract_action_version(step.uses)
                IF action_ref == "main" OR action_ref == "master" OR action_ref == "latest":
                    security_errors.append({
                        "type": "UNPINNED_ACTION",
                        "job": job.name,
                        "action": step.uses,
                        "severity": "MEDIUM",
                        "message": f"Action '{step.uses}' should be pinned to a specific version",
                        "fixable": true
                    })
    
    # Rule 3: Secret references
    secret_refs = extract_secret_references(parsed_yaml)
    declared_secrets = technology_context.inferred_secrets
    FOR ref in secret_refs:
        IF ref not in declared_secrets:
            security_errors.append({
                "type": "UNDECLARED_SECRET",
                "secret": ref,
                "severity": "WARNING",
                "message": f"Secret reference '${{{{ secrets.{ref} }}}}' is not in the inferred secrets list",
                "fixable": false
            })
    
    # Rule 4: Permissions block
    IF "permissions" not in parsed_yaml:
        security_errors.append({
            "type": "MISSING_PERMISSIONS",
            "severity": "MEDIUM",
            "message": "Workflow should define explicit permissions (minimum: contents: read)",
            "fixable": true
        })
    ELIF parsed_yaml.permissions.get("contents") not in ["read", None]:
        security_errors.append({
            "type": "OVERLY_PERMISSIVE",
            "severity": "HIGH",
            "message": "Workflow permissions should default to 'contents: read'",
            "fixable": true
        })
    
    RETURN {{valid: len(security_errors) == 0, errors: security_errors}}
```

**Step 4: Semantic Validation (LLM-based)**
```
FUNCTION validate_semantics(workflow_yaml, technology_context):
    1. CONSTRUCT prompt:
       """
       SYSTEM: You are a DevSecOps quality assurance auditor.
       Review this GitHub Actions workflow and identify LOGICAL ERRORS.
       A logical error means: the build/test/security steps would NOT work correctly
       for the described technology stack.
       
       Technology Stack: {technology_context}
       
       Workflow YAML:
       {workflow_yaml}
       
       Return JSON:
       {{
         "semantically_correct": bool,
         "issues": [
           {{
             "severity": "error"|"warning",
             "location": "job_name.step_name",
             "description": str,
             "suggested_fix": str|null
           }}
         ]
       }}
       """
    
    2. CALL OpenRouter LLM (model: lightweight)
    3. PARSE response
    4. RETURN semantic_validation_result
```

### Decision Rules

| Condition | Action |
|---|---|
| Syntax validation FAILS | Abort remaining validations; route to Repair Agent immediately |
| Schema validation has > 5 errors | Flag as "likely hallucinated"; re-generate from scratch |
| All security tools are missing | Prompt user: "No security tools configured. This is a non-secure workflow." |
| Semantic validation finds "error"-level issues | Block PR creation; route to Repair Agent |
| All validations pass | Set `validation_passed = true`; enable PR creation |

### Outputs

```json
{
  "validation_passed": false,
  "errors": [
    {
      "type": "SCHEMA_ERROR",
      "path": "jobs → build-and-test",
      "message": "'runs-on' is a required property",
      "fixable": true
    },
    {
      "type": "UNPINNED_ACTION",
      "job": "trivy-dependency-scan",
      "action": "aquasecurity/trivy-action@master",
      "severity": "MEDIUM",
      "message": "Action 'aquasecurity/trivy-action@master' should be pinned",
      "fixable": true
    }
  ],
  "warnings": [],
  "semantic_issues": [],
  "total_checks_run": 4,
  "checks_passed": 2
}
```

---

## 5.4 Workflow Repair Logic Flow

### Inputs
| Input | Source | Format |
|---|---|---|
| Original Workflow YAML | Generator Agent output | String (YAML) |
| Validation Errors | Validator Agent output | `[{type, path/location, message, fixable}]` |
| Technology Context | Analysis Results | JSON |
| Repair History | Agent State (from previous iterations) | `[{attempt, changes_made, success}]` |

### Processes

**Step 1: Error Classification**
```
FUNCTION classify_errors(validation_errors):
    classified = {
        "syntax": [],
        "schema": [],
        "security_policy": [],
        "semantic": []
    }
    
    FOR error in validation_errors:
        MATCH error.type:
            CASE "SYNTAX_ERROR": classified.syntax.append(error)
            CASE "SCHEMA_ERROR": classified.schema.append(error)
            CASE "MISSING_SECURITY_TOOL" | "UNPINNED_ACTION" | "MISSING_PERMISSIONS" | "OVERLY_PERMISSIVE":
                classified.security_policy.append(error)
            CASE "SEMANTIC_ERROR": classified.semantic.append(error)
            CASE "UNDECLARED_SECRET": classified.security_policy.append(error)
    
    RETURN classified
```

**Step 2: Prioritized Repair Strategy**
```
FUNCTION repair_workflow(original_yaml, classified_errors, repair_attempt):
    1. DETECT infinite loop:
       HASH current (original_yaml + errors)
       IF hash exists in repair_history: ABORT ("detected repair loop")
    
    2. PRIORITIZE repairs:
       repair_order = ["syntax", "schema", "security_policy", "semantic"]
    
    3. FOR category in repair_order:
         IF classified_errors[category] is not empty:
             repaired = apply_category_repair(original_yaml, category, classified_errors[category])
             IF repaired differs from original: BREAK (one category per iteration)
    
    4. RETURN repaired_yaml
```

**Step 3: Category-Specific Repair Logic**

**3a. Syntax Repair**
```
FUNCTION repair_syntax(yaml_string, syntax_errors):
    1. FOR each syntax_error:
       MATCH error message pattern:
         CASE "mapping values are not allowed":
           FIX: Ensure proper indentation (2 spaces) → Apply YAML auto-formatter
         CASE "found unexpected end of stream":
           FIX: Check for unclosed quotes/brackets → Use regex to find and close
         CASE "found character '\\t'":
           FIX: Replace tabs with 2 spaces
         CASE other:
           ATTEMPT: Use LLM with few-shot prompt containing (broken_yaml, fixed_yaml) pairs
    
    2. RE-PARSE to verify fix
    3. RETURN repaired_yaml
```

**3b. Schema Repair**
```
FUNCTION repair_schema(parsed_yaml, schema_errors):
    """Schema errors are deterministic — the system can fix them without LLM."""
    
    FOR error in schema_errors:
        MATCH error.message:
            CASE contains "required property 'runs-on'":
                SET parsed_yaml["jobs"][job_name]["runs-on"] = "ubuntu-latest"
            
            CASE contains "required property 'steps'":
                SET parsed_yaml["jobs"][job_name]["steps"] = []
            
            CASE contains "is not valid under any of the given schemas" for trigger:
                FIX trigger to valid value: "push" | "pull_request" | "schedule" | "workflow_dispatch"
            
            CASE contains "should be one of":
                EXTRACT valid options from error message
                SET to first valid option
            
            CASE other:
                USE LLM to suggest fix for this schema violation
    
    2. RETURN dump_yaml(parsed_yaml)
```

**3c. Security Policy Repair**
```
FUNCTION repair_security_policy(parsed_yaml, security_errors):
    FOR error in security_errors:
        MATCH error.type:
            CASE "MISSING_SECURITY_TOOL":
                ADD tool-specific job block to parsed_yaml["jobs"]
                (using pre-defined templates for Semgrep, Gitleaks, Trivy, CodeQL, Dependency Review)
            
            CASE "UNPINNED_ACTION":
                REPLACE version @master → @v4 (for official GitHub actions)
                OR @master → @v2 (for gitleaks-action)
                OR fetch latest tag from GitHub API and pin
            
            CASE "MISSING_PERMISSIONS":
                ADD permissions block:
                parsed_yaml["permissions"] = {"contents": "read"}
            
            CASE "OVERLY_PERMISSIVE":
                SET parsed_yaml["permissions"]["contents"] = "read"
    
    2. RETURN dump_yaml(parsed_yaml)
```

**3d. Semantic Repair**
```
FUNCTION repair_semantics(workflow_yaml, semantic_errors, tech_context):
    """Semantic errors require LLM reasoning."""
    
    1. CONSTRUCT prompt:
       """
       SYSTEM: You are fixing logical errors in a GitHub Actions workflow.
       
       Technology Stack: {tech_context}
       
       Current Workflow (with errors):
       {workflow_yaml}
       
       Errors to fix:
       {json.dumps(semantic_errors)}
       
       Return the FULL corrected workflow YAML. Only fix the specified errors.
       Do not make unnecessary changes.
       """
    
    2. CALL OpenRouter LLM (model: secondary)
    3. RETURN LLM output (after YAML cleaning)
```

### Decision Rules (Iteration Control)

| Condition | Action |
|---|---|
| `repair_attempt >= 3` | Stop repair; set status to "repair_failed"; return to user for manual review |
| Repaired YAML is identical to original (hash check) | Detect repair loop; set status to "repair_stuck"; return to user |
| All fixable errors resolved but non-fixable remain | Set status to "partial_repair"; list remaining issues for user |
| All errors resolved | Set status to "repair_complete"; re-route to Validator |

### Outputs

```json
{
  "repair_status": "repair_complete",
  "attempts_used": 1,
  "changes_made": [
    {
      "type": "SCHEMA_FIX",
      "description": "Added 'runs-on: ubuntu-latest' to job 'build-and-test'",
      "location": "jobs.build-and-test.runs-on"
    },
    {
      "type": "VERSION_PIN",
      "description": "Pinned 'aquasecurity/trivy-action@master' to '@v0.24.0'",
      "location": "jobs.trivy-dependency-scan.steps[1].uses"
    }
  ],
  "remaining_errors": [],
  "repaired_yaml": "name: DevSecOps Pipeline...\n..."
}
```

---

## 5.5 Risk Scoring Logic Flow

### Inputs
| Input | Source | Format |
|---|---|---|
| Scan Findings | Workflow execution → parsed SARIF/Gitleaks/Trivy output | `[{tool, rule_id, severity, file_path, line, cwe_id, cvss_score}]` |
| Repository Metadata | Database | `{language, size, age_days, commit_frequency}` |
| Historical Findings | Database (previous scans) | JSON |
| Triage Status | User actions | `[{finding_id, status: "false_positive"|"accepted_risk"|"fixed"|"open"}]` |

### Processes

**Step 1: Weighted Severity Scoring**
```
FUNCTION calculate_weighted_score(findings):
    """Base risk score from finding severities with weighting."""
    
    score = 0
    severity_weights = {
        "critical": 10,
        "high": 5,
        "medium": 2,
        "low": 1,
        "info": 0.5
    }
    
    FOR finding in findings:
        IF finding.triage_status == "false_positive": CONTINUE
        IF finding.triage_status == "fixed": weight_modifier = 0.0
        ELSE: weight_modifier = 1.0
        
        weight = severity_weights[finding.severity] * weight_modifier
        
        # Apply CVSS multiplier if available
        IF finding.cvss_score:
            weight *= (finding.cvss_score / 10.0)
        
        # Apply CWE criticality multiplier
        IF finding.cwe_id in KNOWN_CRITICAL_CWES:  # e.g., CWE-89 (SQLi), CWE-79 (XSS)
            weight *= 1.5
        
        # Apply file exposure multiplier
        IF is_public_facing_file(finding.file_path):
            weight *= 1.3
        
        score += weight
    
    RETURN score
```

**Step 2: Normalization to 0-100 Scale**
```
FUNCTION normalize_risk_score(raw_score, findings_count):
    """Normalize to a human-readable 0-100 scale."""
    
    # Theoretical maximum score (worst-case scenario)
    max_score = findings_count * 10 * 1.5 * 1.3  # All critical, critical CWE, public-facing
    
    IF max_score == 0: RETURN 0.0
    
    normalized = (raw_score / max_score) * 100
    RETURN round(min(normalized, 100.0), 1)
```

**Step 3: Risk Category Mapping**
```
FUNCTION categorize_risk(score):
    MATCH score:
        CASE >= 75: return "CRITICAL"
        CASE >= 50: return "HIGH"
        CASE >= 25: return "MEDIUM"
        CASE >= 10: return "LOW"
        CASE < 10:  return "MINIMAL"
```

**Step 4: Trend Analysis**
```
FUNCTION calculate_trend(current_score, historical_scores):
    IF len(historical_scores) < 2:
        RETURN "insufficient_data"
    
    slope = linear_regression(historical_scores + [current_score])
    
    MATCH slope:
        CASE > 5:   return "worsening_significantly"
        CASE > 1:   return "worsening"
        CASE -1..1: return "stable"
        CASE < -5:  return "improving_significantly"
        CASE < -1:  return "improving"
```

**Step 5: LLM-Augmented Risk Assessment**
```
FUNCTION llm_risk_assessment(findings, repository_metadata):
    """Additional qualitative risk analysis with LLM."""
    
    # Only invoke for medium+ risk
    IF normalize_risk_score < 25: SKIP LLM assessment
    
    1. CONSTRUCT prompt:
       """
       SYSTEM: You are a security risk assessor. Analyze the following
       security findings and provide a qualitative risk assessment.
       
       Repository context: {repo_metadata}
       
       Findings summary:
       - Critical: {count_critical}
       - High: {count_high}
       - Medium: {count_medium}
       - Low: {count_low}
       
       Top 5 findings:
       {top_findings_summary}
       
       Return JSON:
       {
         "overall_assessment": str,  # 2-3 sentence executive summary
         "key_concerns": [str],      # Top 3 concerns
         "attack_surface": str,      # Assessment of attack surface
         "compliance_impact": str|null,  # GDPR/SOC2/PCI implication
         "urgency": "immediate"|"high"|"moderate"|"low"
       }
       """
    
    2. CALL OpenRouter LLM (model: primary)
    3. PARSE response
    4. RETURN qualitative_assessment
```

### Decision Rules

| Condition | Action |
|---|---|
| No findings exist | Risk score = 0; category = "MINIMAL"; show "All Clear" badge |
| Only info/low findings | Skip LLM assessment; return base score |
| Critical finding detected | Auto-escalate; set urgency = "immediate"; send notification |
| Trend is "worsening_significantly" | Flag dashboard with red alert; suggest urgent review |
| False positive rate > 30% | Recommend security tool configuration review |

### Outputs

```json
{
  "repository_id": "repo-5678",
  "scan_id": "scan-9012",
  "timestamp": "2026-06-08T10:30:00Z",
  "risk_score": 67.3,
  "risk_category": "HIGH",
  "risk_trend": "worsening",
  "finding_counts": {
    "critical": 2,
    "high": 5,
    "medium": 12,
    "low": 23,
    "info": 40,
    "false_positives": 8
  },
  "top_findings": [
    {
      "tool": "trivy",
      "cve_id": "CVE-2024-1234",
      "severity": "critical",
      "cvss_score": 9.8,
      "file": "package-lock.json",
      "package": "lodash@4.17.19"
    }
  ],
  "qualitative_assessment": {
    "overall_assessment": "The repository has a HIGH risk profile, primarily driven by critical dependency vulnerabilities in lodash and express. The risk trend is worsening, indicating new vulnerabilities are being introduced faster than they are being remediated.",
    "key_concerns": [
      "Critical RCE vulnerability in lodash < 4.17.21 (CVE-2024-1234)",
      "Multiple hardcoded secrets detected by Gitleaks in test fixtures",
      "XSS vulnerabilities in user-facing React components"
    ],
    "attack_surface": "Web application with public-facing endpoints, containerized deployment",
    "compliance_impact": "Current vulnerability posture would fail SOC 2 Type II audit criteria for vulnerability management",
    "urgency": "high"
  }
}
```

---

## 5.6 Recommendation Generation Logic Flow

### Inputs
| Input | Source | Format |
|---|---|---|
| Findings (filtered to HIGH/CRITICAL) | Risk Scoring output | JSON |
| Technology Context | Analysis Results | JSON |
| Repository Structure | File tree from analysis | JSON |
| Previous Recommendations | Database | `[{finding_id, recommendation, status}]` |

### Processes

**Step 1: Finding Grouping**
```
FUNCTION group_findings(findings):
    groups = {
        "dependency_updates": [],    # Trivy/Dependabot findings
        "code_fixes": [],            # Semgrep/CodeQL findings
        "secret_removal": [],        # Gitleaks findings
        "config_changes": [],        # Trivy config scan, Hadolint findings
        "ci_cd_hardening": []        # Workflow policy violations
    }
    
    FOR finding in findings:
        MATCH finding.tool:
            CASE "trivy" (fs scan):      groups.dependency_updates.append(finding)
            CASE "trivy" (config scan):  groups.config_changes.append(finding)
            CASE "semgrep":              groups.code_fixes.append(finding)
            CASE "codeql":               groups.code_fixes.append(finding)
            CASE "gitleaks":             groups.secret_removal.append(finding)
            CASE "dependency-review":    groups.dependency_updates.append(finding)
    
    RETURN groups
```

**Step 2: Template-Based Quick Recommendations**
```
FUNCTION generate_quick_recommendations(grouped_findings):
    recommendations = []
    
    # Dependency updates (deterministic, no LLM needed)
    FOR finding in grouped_findings.dependency_updates:
        rec = {
            "type": "dependency_update",
            "finding_id": finding.id,
            "package": finding.package_name,
            "current_version": finding.current_version,
            "fixed_version": finding.fixed_version,
            "cve_id": finding.cve_id,
            "action": f"Upgrade {finding.package_name} from {finding.current_version} to {finding.fixed_version}",
            "auto_fixable": true,
            "command": get_upgrade_command(finding.package_manager, finding.package_name, finding.fixed_version)
        }
        recommendations.append(rec)
    
    # Secret removal (actionable, minimal LLM)
    FOR finding in grouped_findings.secret_removal:
        rec = {
            "type": "secret_removal",
            "finding_id": finding.id,
            "file": finding.file_path,
            "line": finding.line_number,
            "action": f"Remove hardcoded secret at {finding.file_path}:{finding.line_number} and use environment variable or secrets manager",
            "auto_fixable": false,  # Requires human understanding of secret context
            "command": None
        }
        recommendations.append(rec)
    
    RETURN recommendations
```

**Step 3: LLM-Powered Code Fix Generation**
```
FUNCTION generate_code_fix_recommendations(code_findings, repo_context):
    """Generate specific code fix suggestions using LLM."""
    
    FOR finding in code_findings:
        1. FETCH file content for finding.file_path (from database/clone)
        2. EXTRACT surrounding code context (10 lines before/after finding.line_number)
        
        3. CONSTRUCT prompt:
           """
           SYSTEM: You are a secure code review expert. A security scanner 
           found a potential vulnerability. Generate a specific code fix.
           
           FINDING:
           - Tool: {finding.tool}
           - Rule: {finding.rule_id}
           - Severity: {finding.severity}
           - Description: {finding.description}
           - CWE: {finding.cwe_id}
           
           CODE CONTEXT (file: {finding.file_path}):
           ```{file_extension}
           {code_context}
           ```
           
           Return JSON:
           {
             "explanation": str,           # Why this fix resolves the vulnerability
             "fix_type": "replace"|"insert"|"delete"|"refactor",
             "old_code": str,              # Code to replace (exact match from context)
             "new_code": str,              # Fixed code
             "breaking_change": bool,      # Does this change API behavior?
             "confidence": 0.0-1.0,        # How confident is this fix correct?
             "cwe_reference": str,         # Link to CWE description
             "additional_notes": str|null
           }
           """
        
        4. CALL OpenRouter LLM (model: secondary)
        5. PARSE response
        
        6. VALIDATE fix:
           - old_code must match exactly what's in the file
           - new_code must be syntactically valid (parse with language parser if available)
           - IF confidence < 0.7: flag as "requires_review"
        
        7. ADD to recommendations list
    
    RETURN recommendations
```

**Step 4: Configuration Change Recommendations**
```
FUNCTION generate_config_recommendations(config_findings):
    """Generate Dockerfile/K8s/dependency configuration fixes."""
    
    recommendations = []
    
    FOR finding in config_findings:
        # Use LLM for complex config changes
        prompt = f"""
        SYSTEM: Fix this security configuration issue.
        
        Issue: {finding.description}
        File: {finding.file_path}
        Context: {get_file_context(finding)}
        
        Return JSON with: {{explanation, fix_type, old_config, new_config, breaking_change, confidence}}
        """
        
        result = CALL OpenRouter LLM (model: secondary)
        recommendations.append(result)
    
    RETURN recommendations
```

**Step 5: CI/CD Hardening Recommendations**
```
FUNCTION generate_cicd_recommendations(workflow_findings, repo_context):
    recommendations = []
    
    # These are mostly rule-based
    FOR finding in workflow_findings:
        MATCH finding.rule:
            CASE "minimal_permissions":
                rec = "Add explicit `permissions: {{}}` block to workflow and grant only required permissions per job"
            CASE "unpinned_actions":
                rec = f"Pin {finding.action_ref} to a specific SHA for supply chain integrity"
            CASE "missing_codeql":
                rec = "Add CodeQL analysis job to scan for vulnerabilities in your primary language"
            CASE "no_branch_protection":
                rec = "Configure branch protection rules requiring status checks and code review before merge"
        
        recommendations.append(rec)
    
    RETURN recommendations
```

### Decision Rules

| Condition | Action |
|---|---|
| `fixed_version` is a major bump (>1.x to >2.x) | Add "BREAKING CHANGE" warning; flag as "requires_review" |
| LLM confidence < 0.7 for code fix | Do not auto-apply; flag as "review_required" |
| Finding already has a recommendation from previous scan | Skip duplicate; note "previously recommended" |
| File has been deleted since scan | Skip recommendation; note "file no longer exists" |
| Recommendation would modify >10 files | Suggest as a separate refactoring effort; flag as "large_scope" |

### Outputs

```json
{
  "scan_id": "scan-9012",
  "recommendations": [
    {
      "id": "rec-0001",
      "type": "dependency_update",
      "priority": "critical",
      "finding_id": "find-0100",
      "package": "lodash",
      "current_version": "4.17.19",
      "fixed_version": "4.17.21",
      "cve_id": "CVE-2024-1234",
      "auto_fixable": true,
      "command": "npm install lodash@4.17.21",
      "breaking_change": false,
      "explanation": "lodash versions prior to 4.17.21 are vulnerable to prototype pollution (CVE-2024-1234). Upgrading to 4.17.21 resolves this critical vulnerability with no breaking changes.",
      "cwe_reference": "https://cwe.mitre.org/data/definitions/1321.html"
    },
    {
      "id": "rec-0002",
      "type": "code_fix",
      "priority": "high",
      "finding_id": "find-0200",
      "file": "src/components/UserProfile.tsx",
      "line": 42,
      "explanation": "User input is being directly rendered using dangerouslySetInnerHTML without sanitization. This creates a reflected XSS vulnerability. The fix uses DOMPurify to sanitize the input before rendering.",
      "fix_type": "replace",
      "old_code": "<div dangerouslySetInnerHTML={{ __html: user.bio }} />",
      "new_code": "import DOMPurify from 'dompurify';\n\n<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(user.bio) }} />",
      "breaking_change": false,
      "confidence": 0.92,
      "cwe_reference": "https://cwe.mitre.org/data/definitions/79.html"
    },
    {
      "id": "rec-0003",
      "type": "secret_removal",
      "priority": "critical",
      "finding_id": "find-0300",
      "file": "config/test.env",
      "line": 5,
      "action": "Remove hardcoded AWS access key at config/test.env:5. Move to GitHub Secrets and reference via ${{ secrets.AWS_ACCESS_KEY_ID }}",
      "auto_fixable": false
    }
  ],
  "summary": {
    "total": 12,
    "auto_fixable": 7,
    "requires_review": 5,
    "by_priority": {"critical": 3, "high": 5, "medium": 4}
  }
}
```

---

## 5.7 Workflow Monitoring Logic Flow

### Inputs
| Input | Source | Format |
|---|---|---|
| PR Metadata | Database (pull_requests table) | `{pr_number, repo_owner, repo_name, head_sha}` |
| Workflow Run ID | GitHub Actions (triggered by PR push) | `run_id: int` |

### Processes

**Step 1: Polling Loop Initialization**
```
FUNCTION start_monitoring(pr_metadata):
    1. CREATE WorkflowRun record in database: status = "queued"
    2. ENQUEUE monitoring job to Redis queue: {type: "monitoring", pr_id, repo, run_id}
    3. Worker picks up job: ENTER polling_loop()
```

**Step 2: Polling Loop**
```
FUNCTION polling_loop(pr_metadata):
    max_poll_time = 3600  # 1 hour max monitoring
    poll_interval_active = 15  # seconds during active execution
    poll_interval_idle = 60   # seconds when no active jobs
    start_time = now()
    
    WHILE (now() - start_time) < max_poll_time:
        1. CALL GitHub API:
           GET /repos/{owner}/{repo}/commits/{head_sha}/check-runs
           Headers: Accept: application/vnd.github+json
        
        2. IF rate-limited (403):
             wait_until = parse_rate_limit_reset(response.headers)
             SLEEP until wait_until
             CONTINUE
        
        3. PARSE check_runs from response:
           FOR check in check_runs:
               UPDATE database: check_runs table (UPSERT)
               IF check.status changed:
                   PUBLISH WebSocket event to connected clients
        
        4. DETERMINE workflow_completion:
           all_done = ALL checks have status == "completed"
           has_failure = ANY check has conclusion in ["failure", "timed_out", "cancelled"]
           
           IF all_done:
               BREAK polling_loop
        
        5. DETERMINE next_poll_interval:
           any_active = ANY check has status in ["queued", "in_progress"]
           interval = poll_interval_active IF any_active ELSE poll_interval_idle
        
        6. SLEEP interval
    
    # After loop exits
    PROCESS workflow_results(pr_metadata)
```

**Step 3: Artifact Collection**
```
FUNCTION process_workflow_results(pr_metadata):
    1. FETCH workflow run artifacts:
       GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts
    
    2. FOR each artifact matching security tool output patterns:
       MATCH artifact.name:
           CASE "semgrep.sarif":   PARSE as SARIF → extract findings
           CASE "gitleaks.json":   PARSE as Gitleaks JSON → extract findings
           CASE "trivy-*.sarif":   PARSE as SARIF → extract findings
           CASE "codeql-*.sarif":  PARSE as SARIF → extract findings
    
    3. DOWNLOAD artifact ZIP
    4. EXTRACT and parse
    5. DEDUPLICATE findings across tools
    6. PERSIST findings to database (findings table)
    7. UPDATE workflow_run status = "completed"
    8. TRIGGER Risk Assessment Agent
    9. TRIGGER Recommendation Agent
    10. SEND notification to user
```

**Step 4: Real-Time Status Updates**
```
FUNCTION push_status_update(pr_metadata, check_runs):
    1. BUILD status summary:
       {
         "run_id": run_id,
         "status": aggregate_status,  # "queued"|"in_progress"|"completed"|"failed"
         "checks": [
           {name, status, conclusion, started_at, completed_at, html_url}
         ],
         "progress": {
            "total_jobs": len(check_runs),
            "completed": count_completed(check_runs),
            "passed": count_passed(check_runs),
            "failed": count_failed(check_runs)
         }
       }
    
    2. PUBLISH to Redis channel: f"workflow:{pr_metadata.id}"
    3. WebSocket handler picks up and pushes to connected clients
    4. UPDATE frontend in real-time (progress bar, check icons)
```

### Failure Detection & Recovery

| Failure | Detection | Recovery |
|---|---|---|
| Workflow hangs (no check update > 30 min) | Timer in polling loop | Mark as "stuck"; offer user to cancel and re-trigger |
| All checks complete but no security artifacts found | Post-loop artifact count == 0 | Mark as "incomplete_scan"; flag for investigation |
| Artifact download fails (GitHub 404) | HTTP error on artifact fetch | Retry 3x; if all fail, mark as "artifact_missing" |
| SARIF parsing fails | SARIF schema validation error | Log raw artifact for manual inspection; mark partially parsed |
| Redis publish fails | Connection error | Fall back to database-only updates; client polls API |

### Outputs (DB Records + Events)

```json
{
  "workflow_run": {
    "id": "run-3456",
    "status": "completed",
    "conclusion": "failure",
    "total_jobs": 7,
    "passed_jobs": 5,
    "failed_jobs": 2,
    "duration_seconds": 485
  },
  "findings_collected": {
    "semgrep": 15,
    "gitleaks": 3,
    "trivy": 8,
    "codeql": 4,
    "dependency_review": 2,
    "total": 32
  },
  "notifications": [
    {"type": "email", "to": "user@example.com", "status": "sent"},
    {"type": "in_app", "message": "Workflow execution completed with 2 failed jobs"}
  ]
}
```
