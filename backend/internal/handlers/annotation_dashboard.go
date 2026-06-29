package handlers

import (
	"regexp"
	"strings"

	"github.com/user/ai-devsecops-backend/internal/services"
)

// scannerKeywords are the only valid sources for security findings.
var scannerKeywords = []string{
	"semgrep", "npm audit", "trivy", "gitleaks", "sarif",
}

var (
	reGithubTokenRequired = regexp.MustCompile(`(?i)GITHUB_TOKEN.*required`)
	reUnexpectedInput     = regexp.MustCompile(`(?i)unexpected input.*args`)
	reCache400            = regexp.MustCompile(`(?i)cache service.*responded with 400`)
	reNodeDeprecated      = regexp.MustCompile(`(?i)Node\.js 20.*deprecated|deprecat.*node`)
	reServiceUnavailable  = regexp.MustCompile(`(?i)aren't available right now|service unavailable|service.*interruption`)
	reScannerOutput       = regexp.MustCompile(`(?i)(semgrep|npm audit|trivy|gitleaks|sarif)`)
	// reWorkflowHNoise matches annotation text that is NOT a real
	// scanner finding — it is just the GitHub Actions runner
	// complaining about a missing artifact, exit code 1, or
	// cancellation. Reviewer feedback: previous code treated these
	// as security findings because the path contained "trivy" or
	// "gitleaks", which inflated the security risk score and
	// produced 13 false positives on a clean run.
	reWorkflowHNoise = regexp.MustCompile(`(?i)(no files were found with the provided path|no artifacts will be uploaded|process completed with exit code|canceling since a higher priority|annotation:)`)
	// reEmptySarifNoise matches "scanner found 0 findings" notices
	// emitted by the upload-sarif fallback step in the generated
	// workflow. These are GitHub Actions notices, NOT security
	// findings. Reviewer feedback: they were being classified as
	// security_finding because the message contained the word
	// "trivy" or "gitleaks", inflating the count with six phantom
	// findings on a clean run.
	reEmptySarifNoise = regexp.MustCompile(`(?i)(found 0 findings|generating empty sarif|did not produce a sarif file|generating empty for upload-sarif|no vulnerabilities? found|no issues? found)`)
)

func annotationSource(annotation services.CheckRunAnnotation) string {
	if s := extractScanner(annotation); s != "" {
		return s
	}
	return "github-actions"
}

func extractScanner(annotation services.CheckRunAnnotation) string {
	text := annotation.Title + " " + annotation.Message + " " + annotation.RawDetails
	// Reviewer feedback: if the annotation is workflow-side noise
	// (missing artifact, exit code 1, cancellation), the scanner
	// keyword in the path is incidental — the annotation is NOT
	// a scanner finding. Return empty so the caller treats it as
	// a workflow config issue instead of a security finding.
	if reWorkflowHNoise.MatchString(text) {
		return ""
	}
	for _, kw := range scannerKeywords {
		if strings.Contains(strings.ToLower(text), kw) {
			return kw
		}
	}
	if m := reScannerOutput.FindString(text); m != "" {
		return strings.ToLower(m)
	}
	return ""
}

func annotationSeverity(level string) string {
	switch strings.ToLower(level) {
	case "failure":
		return "high"
	case "warning":
		return "medium"
	case "notice":
		return "low"
	default:
		return "medium"
	}
}

type categorizedAnnotation struct {
	Title       string
	Evidence    string
	Severity    string
	Source      string
	Remediation string
	Category    string
}

// categorizeAnnotations groups annotations into the four dashboard buckets.
// Security Findings are only generated when a real security scanner produced the annotation.
func categorizeAnnotations(annotations []services.CheckRunAnnotation) []categorizedAnnotation {
	type dedupKey struct {
		category string
		title    string
	}
	seen := make(map[dedupKey]bool)
	var result []categorizedAnnotation

	for _, a := range annotations {
		source := annotationSource(a)
		title := a.Title
		if title == "" {
			title = a.Message
			if len(title) > 120 {
				title = title[:120]
			}
		}
		evidence := a.Message
		severity := annotationSeverity(a.AnnotationLevel)
		remediation := suggestRemediation(title, evidence, source)

		category := categorize(a)

		key := dedupKey{category: category, title: title}
		if seen[key] {
			continue
		}
		seen[key] = true

		result = append(result, categorizedAnnotation{
			Title:       title,
			Evidence:    evidence,
			Severity:    severity,
			Source:      source,
			Remediation: remediation,
			Category:    category,
		})
	}

	return result
}

func categorize(a services.CheckRunAnnotation) string {
	text := a.Title + " " + a.Message + " " + a.RawDetails

	// Reviewer feedback: GitHub Actions runner noise (missing
	// artifact, exit code 1, cancellation) was being classified as
	// a security finding because the path contained the word
	// "trivy" or "gitleaks". These are NOT real security findings
	// — they are workflow-side failures. Treat them as workflow
	// config issues, not security findings.
	if reWorkflowHNoise.MatchString(text) {
		return "workflow_config_issue"
	}

	// Reviewer feedback: "X found 0 findings / generating empty
	// SARIF" notices emitted by the upload-sarif fallback step
	// are NOT security findings. They are workflow-side
	// informational notices. Classify them as workflow config
	// issues so the dashboard bucket assignment is correct.
	if reEmptySarifNoise.MatchString(text) {
		return "workflow_config_issue"
	}

	// Security Findings — only from scanner output
	if extractScanner(a) != "" {
		return "security_finding"
	}

	// Workflow Configuration Issues
	if reGithubTokenRequired.MatchString(text) || reUnexpectedInput.MatchString(text) || reCache400.MatchString(text) {
		return "workflow_config_issue"
	}

	// Maintenance Warnings
	if reNodeDeprecated.MatchString(text) {
		return "maintenance_warning"
	}

	// External Service Issues
	if reServiceUnavailable.MatchString(text) {
		return "external_service_issue"
	}

	// Everything else: if annotation level is "failure", treat as workflow config issue
	if a.AnnotationLevel == "failure" {
		return "workflow_config_issue"
	}

	return "maintenance_warning"
}

func suggestRemediation(title, evidence, source string) string {
	text := strings.ToLower(title + " " + evidence + " " + source)

	// Empty-SARIF / "found 0 findings" notices: no remediation
	// is required (the scanner ran clean). Caller is expected to
	// suppress these findings entirely, but we still return an
	// empty string so the UI does not render stale advice.
	if reEmptySarifNoise.MatchString(text) {
		return ""
	}

	// Docker: USER root detected — high severity, A05 Security
	// Misconfiguration. Provide a copy-pasteable fix.
	if strings.Contains(text, "user root") {
		return dockerUserRootRemediation()
	}

	// .env file in git history — high severity, CWE-798 / A02
	// Cryptographic Failures. The secret must be rotated even
	// after the file is removed from HEAD.
	if strings.Contains(text, ".env") && (strings.Contains(text, "git history") || strings.Contains(text, "rotate")) {
		return envInHistoryRemediation()
	}

	switch {
	case strings.Contains(text, "semgrep"):
		return "Review the Semgrep rule output and fix the identified code pattern. Run `semgrep --config auto` locally to validate."
	case strings.Contains(text, "npm audit"):
		return "Run `npm audit fix` or update the vulnerable package to the recommended version. Review `package-lock.json` for pinned versions."
	case strings.Contains(text, "trivy"):
		return "Update the container image or dependency to the version recommended by Trivy. Rebuild and re-scan to confirm."
	case strings.Contains(text, "gitleaks"):
		return "Remove the detected secret from the codebase. Use environment variables or GitHub Secrets instead. Run `gitleaks detect --verbose` locally."
	case strings.Contains(text, "sarif"):
		return "Review the SARIF results and address each code quality or security finding. Integrate with GitHub Code Scanning for tracking."
	case strings.Contains(text, "github_token"):
		return "Ensure the workflow has `permissions: contents: read` and uses `GITHUB_TOKEN` via `${{ secrets.GITHUB_TOKEN }}` instead of a custom token."
	case strings.Contains(text, "unexpected input"):
		return "Check the workflow YAML for misspelled or unsupported action inputs. Compare the action's README for the correct parameter names."
	case strings.Contains(text, "cache service"):
		return "Retry the workflow run. If the issue persists, clear the Actions cache under the repository settings page."
	case strings.Contains(text, "deprecated") || strings.Contains(text, "node.js 20"):
		return "Update the action to a version that uses a newer Node.js runtime. Check the action's repository for migration guidance."
	case strings.Contains(text, "service") && (strings.Contains(text, "unavailable") || strings.Contains(text, "interruption")):
		return "This is a transient GitHub service interruption. Re-run the workflow after a few minutes."
	default:
		return ""
	}
}

func buildDashboardFromAnnotations(annotations []services.CheckRunAnnotation) DashboardFindings {
	categorized := categorizeAnnotations(annotations)

	var security, config, maintenance, external []Finding

	for _, c := range categorized {
		// Reviewer feedback: "scanner found 0 findings / generating
		// empty SARIF" notices are GitHub Actions runner output,
		// not real security findings. Drop them from every bucket
		// so they do not inflate the dashboard counts.
		if reEmptySarifNoise.MatchString(c.Title + " " + c.Evidence) {
			continue
		}
		f := Finding{
			Title:                     c.Title,
			Evidence:                  c.Evidence,
			Severity:                  c.Severity,
			SourceTool:                c.Source,
			RemediationRecommendation: c.Remediation,
			Type:                      c.Category,
		}
		if f.Severity == "" {
			f.Severity = "medium"
		}
		// Look up original annotation to get file path and line number
		for _, a := range annotations {
			title := a.Title
			if title == "" {
				if len(a.Message) > 120 {
					title = a.Message[:120]
				} else {
					title = a.Message
				}
			}
			if title == c.Title && a.Message == c.Evidence {
				if a.Path != "" || a.StartLine > 0 {
					f.FileLocation = a.Path
					f.Line = a.StartLine
				}
				break
			}
		}
		switch c.Category {
		case "security_finding":
			security = append(security, f)
		case "workflow_config_issue":
			config = append(config, f)
		case "maintenance_warning":
			maintenance = append(maintenance, f)
		case "external_service_issue":
			external = append(external, f)
		}
	}

	message := ""
	if len(security) == 0 {
		message = "No validated security findings detected. Workflow issues may still exist."
	}

	return DashboardFindings{
		SecurityFindings:      security,
		WorkflowConfigIssues:  config,
		MaintenanceWarnings:   maintenance,
		ExternalServiceIssues: external,
		SecurityCount:         len(security),
		WorkflowConfigCount:   len(config),
		MaintenanceCount:      len(maintenance),
		ExternalCount:         len(external),
		TotalCount:            len(security) + len(config) + len(maintenance) + len(external),
		Message:               message,
	}
}

// MergeAnnotationsWithAIDashboard merges AI-generated findings with annotation-derived dashboards.
// Annotation evidence takes priority for the dashboard, but AI findings are preserved in the findings list.
func mergeAnnotationsWithAIDashboard(aiDashboard DashboardFindings, annotationDashboard DashboardFindings) DashboardFindings {
	// Start from annotation dashboard (evidence-based)
	result := annotationDashboard

	// Merge AI security findings into the findings list (not the dashboard)
	// The dashboard buckets are evidence-based from annotations
	if len(aiDashboard.SecurityFindings) > 0 && len(result.SecurityFindings) == 0 {
		result.SecurityFindings = aiDashboard.SecurityFindings
		result.SecurityCount = len(aiDashboard.SecurityFindings)
	}

	// If AI provided more config issues, merge them
	if len(aiDashboard.WorkflowConfigIssues) > len(result.WorkflowConfigIssues) {
		result.WorkflowConfigIssues = aiDashboard.WorkflowConfigIssues
		result.WorkflowConfigCount = len(aiDashboard.WorkflowConfigIssues)
	}

	result.TotalCount = result.SecurityCount + result.WorkflowConfigCount + result.MaintenanceCount + result.ExternalCount

	if len(result.SecurityFindings) == 0 && result.Message == "" {
		result.Message = "No validated security findings detected. Workflow issues may still exist."
	}

	return result
}

// dockerUserRootRemediation returns the markdown-formatted
// remediation for the "USER root detected — should use non-root
// user" annotation. The recommendation is rendered as markdown by
// the frontend (FindingsTable) and contains a before/after code
// snippet the user can paste into their Dockerfile.
func dockerUserRootRemediation() string {
	var b strings.Builder
	b.WriteString("**Switch to a non-root USER in your Dockerfile.**\n\n")
	b.WriteString("Running as root inside the container means any code-injection vulnerability ")
	b.WriteString("grants the attacker full container privileges (CWE-250, OWASP A05:2021).\n\n")
	b.WriteString("**Steps**\n")
	b.WriteString("1. Create a dedicated user near the top of the Dockerfile.\n")
	b.WriteString("2. Drop privileges with `USER` before the `CMD`/`ENTRYPOINT`.\n")
	b.WriteString("3. Make sure `/app` (or your workdir) is owned by that user.\n\n")
	b.WriteString("**Before**\n")
	b.WriteString("```dockerfile\n")
	b.WriteString("FROM node:20\n")
	b.WriteString("WORKDIR /app\n")
	b.WriteString("COPY . .\n")
	b.WriteString("RUN npm ci --omit=dev\n")
	b.WriteString("USER root\n")
	b.WriteString("CMD [\"node\", \"server.js\"]\n")
	b.WriteString("```\n\n")
	b.WriteString("**After**\n")
	b.WriteString("```dockerfile\n")
	b.WriteString("FROM node:20\n")
	b.WriteString("WORKDIR /app\n")
	b.WriteString("COPY --chown=node:node . .\n")
	b.WriteString("RUN npm ci --omit=dev\n")
	b.WriteString("USER node\n")
	b.WriteString("CMD [\"node\", \"server.js\"]\n")
	b.WriteString("```\n\n")
	b.WriteString("Reference: <https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user>\n")
	return b.String()
}

// envInHistoryRemediation returns the markdown-formatted
// remediation for the ".env file found in git history" PCI-DSS
// annotation. The secret must be rotated even after the file is
// removed from HEAD.
func envInHistoryRemediation() string {
	var b strings.Builder
	b.WriteString("**Remove .env from history and rotate every committed secret.**\n\n")
	b.WriteString("Files matching `.env` contain credentials. Once committed, they are ")
	b.WriteString("visible in the git history forever, even after deletion in HEAD ")
	b.WriteString("(CWE-798, OWASP A02:2021).\n\n")
	b.WriteString("**Steps**\n")
	b.WriteString("1. Add `.env` to `.gitignore` *first* so it is never re-tracked.\n")
	b.WriteString("```gitignore\n")
	b.WriteString("# Local environment files — never commit\n")
	b.WriteString(".env\n")
	b.WriteString(".env.*\n")
	b.WriteString("!.env.example\n")
	b.WriteString("```\n")
	b.WriteString("2. Strip the file from history with `git filter-repo`:\n")
	b.WriteString("```bash\n")
	b.WriteString("git filter-repo --path .env --invert-paths\n")
	b.WriteString("git push origin --force --all\n")
	b.WriteString("```\n")
	b.WriteString("3. **Rotate every secret that was ever stored in that file** — ")
	b.WriteString("database passwords, API keys, JWT signing keys, third-party ")
	b.WriteString("tokens. The old values must be considered compromised.\n")
	b.WriteString("4. Add `gitleaks` to a pre-commit hook to prevent regressions.\n\n")
	b.WriteString("Reference: <https://github.com/gitleaks/gitleaks#pre-commit-hook>\n")
	return b.String()
}
