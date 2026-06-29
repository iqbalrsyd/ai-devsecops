package handlers

import (
	"strings"
	"testing"

	"github.com/user/ai-devsecops-backend/internal/services"
)

// TestCategorize_RejectsGitHubRunnerNoise ensures that annotations
// about missing artifacts, exit code 1, and cancellation are
// classified as workflow_config_issue, NOT security_finding.
//
// Reviewer feedback: a previous version of this code matched the
// substring "trivy" or "gitleaks" in the artifact path and
// classified the "No files were found with the provided path:
// trivy-image-results.txt" annotation as a real scanner finding,
// producing 13 false positives on a clean run.
func TestCategorize_RejectsGitHubRunnerNoise(t *testing.T) {
	cases := []struct {
		name        string
		title       string
		message     string
		wantCat     string
		wantScanner string
	}{
		{
			name:        "missing artifact path",
			title:       "Annotation: No files were found with the provided path: trivy-image-results.txt. No artifact",
			message:     "No files were found with the provided path: trivy-image-results.txt. No artifacts will be uploaded.",
			wantCat:     "workflow_config_issue",
			wantScanner: "",
		},
		{
			name:        "process exit 1",
			title:       "Annotation: Process completed with exit code 1.",
			message:     "Process completed with exit code 1.",
			wantCat:     "workflow_config_issue",
			wantScanner: "",
		},
		{
			name:        "canceling due to concurrency",
			title:       "Annotation: Canceling since a higher priority waiting request exists",
			message:     "Canceling since a higher priority waiting request for CI DevSecOps (javascript)-refs/pull/5/merge exists",
			wantCat:     "workflow_config_issue",
			wantScanner: "",
		},
		{
			name:        "missing fs artifact",
			title:       "Annotation: No files were found with the provided path: trivy-fs-results.txt",
			message:     "No files were found with the provided path: trivy-fs-results.txt. No artifacts will be uploaded.",
			wantCat:     "workflow_config_issue",
			wantScanner: "",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := services.CheckRunAnnotation{
				Title:           tc.title,
				Message:         tc.message,
				AnnotationLevel: "warning",
			}
			gotCat := categorize(a)
			if gotCat != tc.wantCat {
				t.Errorf("categorize(%q) = %q, want %q", tc.name, gotCat, tc.wantCat)
			}
			gotScanner := extractScanner(a)
			if gotScanner != tc.wantScanner {
				t.Errorf("extractScanner(%q) = %q, want %q", tc.name, gotScanner, tc.wantScanner)
			}
		})
	}
}

// TestCategorize_RealScannerFindingKept ensures that genuine
// scanner output is still classified as a security finding.
func TestCategorize_RealScannerFindingKept(t *testing.T) {
	a := services.CheckRunAnnotation{
		Title:           "Semgrep: SQL injection in app.js",
		Message:         "Detected unsanitized SQL query at line 42",
		AnnotationLevel: "warning",
	}
	gotCat := categorize(a)
	if gotCat != "security_finding" {
		t.Errorf("categorize(real scanner) = %q, want security_finding", gotCat)
	}
	gotScanner := extractScanner(a)
	if !strings.Contains(gotScanner, "semgrep") {
		t.Errorf("extractScanner(real scanner) = %q, want 'semgrep'", gotScanner)
	}
}

// TestCategorize_TrivyImageScannerFindingKept ensures that real
// Trivy image scan findings (not "no files found" complaints)
// are still classified as security findings.
func TestCategorize_TrivyImageScannerFindingKept(t *testing.T) {
	a := services.CheckRunAnnotation{
		Title:           "Trivy: CVE-2024-1234 in openssl",
		Message:         "CVE-2024-1234 detected in openssl 1.0.1",
		AnnotationLevel: "warning",
	}
	gotCat := categorize(a)
	if gotCat != "security_finding" {
		t.Errorf("categorize(real trivy) = %q, want security_finding", gotCat)
	}
}

// TestCategorize_EmptySarifNoiseIsWorkflowConfig verifies that
// "scanner found 0 findings / generating empty SARIF" notices
// are classified as workflow_config_issue, not security_finding.
// Reviewer feedback: on a clean run these notices were inflating
// the security count from 2 to 8.
func TestCategorize_EmptySarifNoiseIsWorkflowConfig(t *testing.T) {
	cases := []struct {
		name string
		text string
	}{
		{
			name: "trivy image 0 findings",
			text: "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
		},
		{
			name: "gitleaks 0 findings",
			text: "Gitleaks found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
		},
		{
			name: "trivy dependency scan 0 findings",
			text: "Trivy found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
		},
		{
			name: "semgrep no sarif file",
			text: "Semgrep did not produce a SARIF file. Generating empty SARIF for upload-sarif.",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := services.CheckRunAnnotation{
				Title:           tc.text,
				Message:         tc.text,
				AnnotationLevel: "notice",
			}
			if got := categorize(a); got != "workflow_config_issue" {
				t.Errorf("categorize(%q) = %q, want workflow_config_issue", tc.name, got)
			}
		})
	}
}

// TestBuildDashboard_EmptySarifFindingsDropped verifies that
// the dashboard builder drops empty-SARIF notices entirely, so
// they do not inflate SecurityFindings, WorkflowConfigIssues,
// or any other bucket. Reviewer feedback: the reviewer wanted
// them hidden, not re-bucketed.
func TestBuildDashboard_EmptySarifFindingsDropped(t *testing.T) {
	annotations := []services.CheckRunAnnotation{
		{
			Title:           "Trivy: USER root detected — should use non-root user",
			Message:         "USER root detected — should use non-root user",
			AnnotationLevel: "failure",
		},
		{
			Title:           "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			Message:         "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			AnnotationLevel: "notice",
		},
		{
			Title:           "Gitleaks found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			Message:         "Gitleaks found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			AnnotationLevel: "notice",
		},
		{
			Title:           "Trivy found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			Message:         "Trivy found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			AnnotationLevel: "notice",
		},
	}
	dash := buildDashboardFromAnnotations(annotations)

	// USER root contains the "trivy" keyword so it reaches
	// security_finding. The three "found 0 findings" notices are
	// dropped entirely from every bucket.
	if got := len(dash.SecurityFindings); got != 1 {
		t.Errorf("SecurityFindings len = %d, want 1 (USER root only); titles=%v", got, titlesOf(dash.SecurityFindings))
	}
	for _, f := range dash.SecurityFindings {
		if strings.Contains(f.Title, "found 0 findings") {
			t.Errorf("SecurityFindings contains noise: %q", f.Title)
		}
	}
	if got := dash.SecurityCount; got != 1 {
		t.Errorf("SecurityCount = %d, want 1", got)
	}
	if got := dash.TotalCount; got != 1 {
		t.Errorf("TotalCount = %d, want 1 (noise suppressed)", got)
	}
	// The USER root finding should carry the markdown remediation.
	for _, f := range dash.SecurityFindings {
		if !strings.Contains(f.RemediationRecommendation, "**") {
			t.Errorf("finding %q has non-markdown remediation: %q", f.Title, f.RemediationRecommendation)
		}
		if strings.Contains(f.RemediationRecommendation, "Review the annotation details") {
			t.Errorf("finding %q still has generic remediation: %q", f.Title, f.RemediationRecommendation)
		}
	}
	// Verify no bucket contains the noise at all.
	for _, f := range dash.WorkflowConfigIssues {
		if strings.Contains(f.Title, "found 0 findings") {
			t.Errorf("WorkflowConfigIssues contains noise: %q", f.Title)
		}
	}
	for _, f := range dash.MaintenanceWarnings {
		if strings.Contains(f.Title, "found 0 findings") {
			t.Errorf("MaintenanceWarnings contains noise: %q", f.Title)
		}
	}
	for _, f := range dash.ExternalServiceIssues {
		if strings.Contains(f.Title, "found 0 findings") {
			t.Errorf("ExternalServiceIssues contains noise: %q", f.Title)
		}
	}
}

// TestSuggestRemediation_ProducesMarkdownForKnownFindings verifies
// that the deterministic recommendations for USER root and .env
// in git history contain markdown structure (headings, code
// blocks, references) — not the previous generic single-liner.
func TestSuggestRemediation_ProducesMarkdownForKnownFindings(t *testing.T) {
	cases := []struct {
		name        string
		title       string
		evidence    string
		mustContain []string
		mustSkip    []string
	}{
		{
			name:     "USER root",
			title:    "USER root detected — should use non-root user",
			evidence: "USER root detected — should use non-root user",
			mustContain: []string{
				"**", "Steps", "```dockerfile", "USER node", "docs.docker.com",
			},
			mustSkip: []string{"Review the annotation details"},
		},
		{
			name:     ".env in history",
			title:    ".env file found in git history. Rotate all secrets!",
			evidence: ".env file found in git history. Rotate all secrets!",
			mustContain: []string{
				"**", "```gitignore", "```bash", "git filter-repo", "Rotate", "gitleaks",
			},
			mustSkip: []string{"Review the annotation details"},
		},
		{
			name:        "empty sarif",
			title:       "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			evidence:    "Trivy Image found 0 findings. Generating empty SARIF to satisfy upload-sarif.",
			mustContain: []string{},
			mustSkip:    []string{"Review the annotation details", "Steps"},
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := suggestRemediation(tc.title, tc.evidence, "annotation")
			for _, want := range tc.mustContain {
				if !strings.Contains(got, want) {
					t.Errorf("remediation for %q missing %q\n--- got ---\n%s", tc.name, want, got)
				}
			}
			for _, banned := range tc.mustSkip {
				if strings.Contains(got, banned) {
					t.Errorf("remediation for %q contains banned phrase %q\n--- got ---\n%s", tc.name, banned, got)
				}
			}
		})
	}
}

func titlesOf(findings []Finding) []string {
	out := make([]string, 0, len(findings))
	for _, f := range findings {
		out = append(out, f.Title)
	}
	return out
}
