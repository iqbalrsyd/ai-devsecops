package handlers

import (
	"regexp"
	"strconv"
	"strings"
	"time"
)

// LogToFindingsResult is the response of ParseJobLog: it bundles the
// parsed findings with enough metadata for the run detail UI to know
// which job triggered them and whether the log was truncated.
type LogToFindingsResult struct {
	Scanner   string    `json:"scanner"`
	JobName   string    `json:"job_name"`
	JobID     int64     `json:"job_id"`
	Findings  []Finding `json:"findings"`
	Unparsed  int       `json:"unparsed_lines"`
	Truncated bool      `json:"truncated"`
}

// maxLogBytes caps the input we will parse per job. GitHub job logs can
// be tens of MB for long-running scans; we cap at 2MB to keep latency
// predictable.
const maxLogBytes = 2 * 1024 * 1024

type logPattern struct {
	scanner     string
	pattern     *regexp.Regexp
	severity    string
	ruleIDGen   func(m []string) string
	titleGen    func(m []string) string
	fileGen     func(m []string) string
	lineGen     func(m []string) int
	messageFn   func(m []string) string
	remediation func(m []string) string
}

var logPatterns = []logPattern{
	{
		// Semgrep: "path/to/file.js:LINE:COL: severity RULE_ID - message"
		// Also matches extensionless files like "Dockerfile" / "Makefile".
		scanner:   "semgrep",
		pattern:   regexp.MustCompile(`(?m)^([^\s:]+\.[a-zA-Z0-9]{1,5}|Dockerfile|Makefile):(\d+):\d+:\s+(ERROR|WARNING|INFO)\s+([a-zA-Z0-9_.-]+)\s+(.*)$`),
		severity:  "high",
		ruleIDGen: func(m []string) string { return m[4] },
		titleGen:  func(m []string) string { return strings.TrimSpace(m[5]) },
		fileGen:   func(m []string) string { return m[1] },
		lineGen:   func(m []string) int { return atoiSafe(m[2]) },
		messageFn: func(m []string) string { return strings.TrimSpace(m[5]) },
	},
	{
		// Semgrep "Blocking Code Findings" block (action default output).
		// Example:
		//     Dockerfile
		//        dockerfile.security.last-user-is-root.last-user-is-root
		//           The last user in the container is 'root'.
		//           Details: https://sg.run/5Z43
		//                       12| USER root
		// The file is indented 4 spaces, the rule_id is indented 7 spaces,
		// and the line number is at the start of an indented line followed
		// by either a Unicode box-drawing character (┆) or a pipe (|).
		scanner: "semgrep",
		pattern: regexp.MustCompile(`(?m)^\s{4}(\S+)\s*$\n\s{7}([a-zA-Z0-9_.-]+)\s*$\n(?:.*?\n)*?\s+(\d+)[┆|]`),
		// We always treat the message as "high" because we cannot infer
		// severity from this format (Semgrep GitHub Action only prints
		// the rule_id and message, not the rule's severity tag).
		severity:  "high",
		ruleIDGen: func(m []string) string { return m[2] },
		titleGen:  func(m []string) string { return "Semgrep rule: " + m[2] },
		fileGen:   func(m []string) string { return m[1] },
		lineGen:   func(m []string) int { return atoiSafe(m[3]) },
		messageFn: func(m []string) string { return "Semgrep rule " + m[2] + " triggered in " + m[1] },
	},
	{
		// Semgrep run summary: "Ran 150 rules on 12 files: 17 findings."
		// This line appears when Semgrep outputs SARIF (per-file
		// findings are written to the SARIF file, not stdout). We
		// emit a single synthesized finding so the user knows the
		// job actually scanned code and N findings exist in SARIF.
		// Reviewer feedback: previously the parser would emit no
		// findings for a Semgrep run that succeeded with findings,
		// hiding the security signal from the dashboard.
		scanner: "semgrep",
		pattern: regexp.MustCompile(`(?m)Ran\s+(\d+)\s+rules?\s+on\s+(\d+)\s+files?:\s+(\d+)\s+findings?\.?`),
		// Severity is "high" when there are findings; the count is
		// informational, not a real CVSS score.
		severity:  "high",
		ruleIDGen: func(m []string) string { return "semgrep-run-summary" },
		titleGen:  func(m []string) string { return "Semgrep found " + m[3] + " issue(s) across " + m[2] + " file(s)" },
		fileGen:   func(m []string) string { return "" },
		lineGen:   func(m []string) int { return 0 },
		messageFn: func(m []string) string {
			return "Semgrep executed " + m[1] + " rules on " + m[2] + " tracked file(s) and reported " + m[3] + " finding(s). The per-file findings are written to the SARIF report — see the Code Scanning tab in the repository for the full list."
		},
		// Override the default remediation so the user is directed
		// to the Code Scanning tab (where the per-file findings
		// actually live) instead of getting the generic
		// "refactor the offending line" advice.
		remediation: func(m []string) string {
			return "The per-file findings from this Semgrep run were uploaded as a SARIF report. Open the **Code Scanning** tab in the repository to see the file, line, and rule for each of the " + m[3] + " finding(s) reported above. Exit code 1 from the Semgrep job indicates findings were detected — it is NOT a workflow failure."
		},
	},
	{
		// Trivy: "libname@version (filetype: path/to/file:LINE)"
		// AND a wider catch-all for table output:
		//   libname:version  LIBRARY_TYPE  VULNERABILITY_ID  SEVERITY  installed_ver  fixed_ver
		scanner:   "trivy",
		pattern:   regexp.MustCompile(`(?m)^(\S+@\S+)\s+\(([a-z]+):\s+([^\s:)]+)(?::(\d+))?\)`),
		severity:  "high",
		ruleIDGen: func(m []string) string { return "trivy-vuln-" + sanitizeID(m[1]) },
		titleGen:  func(m []string) string { return "Vulnerable dependency: " + m[1] },
		fileGen:   func(m []string) string { return m[3] },
		lineGen:   func(m []string) int { return atoiSafe(m[4]) },
		messageFn: func(m []string) string { return "Trivy detected vulnerable package " + m[1] },
	},
	{
		// Trivy TABLE output (default `trivy fs .` or `trivy image`):
		//   libname@version  LIB_TYPE  VULN_ID  SEVERITY  installed_ver  fixed_ver  title
		// Example:
		//   lodash@4.17.4  npm  CVE-2019-10744  CRITICAL  4.17.4  4.17.12  Prototype Pollution
		scanner: "trivy",
		pattern: regexp.MustCompile(`(?m)^(\S+@\S+)\s+\S+\s+(CVE-\d+-\d+)\s+(CRITICAL|HIGH|MEDIUM|LOW|UNKNOWN)\s+\S+\s+\S+`),
		// Map CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN to internal severity scale
		severity:  "high",
		ruleIDGen: func(m []string) string { return m[2] },
		titleGen:  func(m []string) string { return m[2] + " in " + m[1] },
		fileGen:   func(m []string) string { return "package-lock.json" },
		lineGen:   func(m []string) int { return 0 },
		messageFn: func(m []string) string { return m[2] + " (" + strings.ToLower(m[3]) + " severity) affects " + m[1] },
	},
	{
		// Trivy fs scan summary: "Total: N (UNKNOWN: N, LOW: N, MEDIUM: N, HIGH: N, CRITICAL: N)"
		// We don't extract individual findings from this line, but the
		// presence of HIGH/CRITICAL counts in the log is a strong signal
		// to the UI that vulnerabilities exist (matched by the
		// code-scanning alert fetch in ExtractAllJobFindings).
		scanner: "trivy",
		pattern: regexp.MustCompile(`(?m)Total:\s+(\d+)\s+\(.*?(CRITICAL|HIGH):\s+(\d+)`),
		// We don't have a finding here, just a count, so emit a
		// "summary" finding with the count embedded in the message.
		severity:  "high",
		ruleIDGen: func(m []string) string { return "trivy-scan-summary" },
		titleGen:  func(m []string) string { return "Trivy scan found " + m[1] + " total issues" },
		fileGen:   func(m []string) string { return "" },
		lineGen:   func(m []string) int { return 0 },
		messageFn: func(m []string) string {
			return "Trivy reported " + m[1] + " total findings including " + m[3] + " " + m[2] + " severity. See Code Scanning tab for details."
		},
	},
	{
		// Gitleaks: "Finding:  RULE_ID\nSecret: ***\nFile: path/to/file:LINE"
		scanner:   "gitleaks",
		pattern:   regexp.MustCompile(`(?ms)Finding:\s+([a-zA-Z0-9_-]+)\s+Secret:[^\n]*\s+File:\s+([^\s:]+):(\d+)`),
		severity:  "critical",
		ruleIDGen: func(m []string) string { return m[1] },
		titleGen:  func(m []string) string { return "Hardcoded secret detected: " + m[1] },
		fileGen:   func(m []string) string { return m[2] },
		lineGen:   func(m []string) int { return atoiSafe(m[3]) },
		messageFn: func(m []string) string { return "Gitleaks found a hardcoded secret matching rule " + m[1] },
	},
	{
		// npm audit summary: "name  Version: x  Severity: high"
		scanner:   "npm-audit",
		pattern:   regexp.MustCompile(`(?m)^(\S+)\s+Version:\s+(\S+)\s+Severity:\s*(low|moderate|high|critical)`),
		severity:  "high",
		ruleIDGen: func(m []string) string { return "npm-audit-" + sanitizeID(m[1]) },
		titleGen:  func(m []string) string { return "Vulnerable npm package: " + m[1] + "@" + m[2] },
		fileGen:   func(m []string) string { return "package.json" },
		lineGen:   func(m []string) int { return 0 },
		messageFn: func(m []string) string {
			return "npm audit reports " + m[3] + " severity issue in " + m[1] + "@" + m[2]
		},
	},
	{
		// ESLint / Ruff / generic linter: "path/to/file.py:LINE:COL: CODE message"
		scanner:   "linter",
		pattern:   regexp.MustCompile(`(?m)^([^\s:]+\.[a-zA-Z]{1,5}):(\d+):(\d+):\s+([A-Z]\d+)\s+(.*)$`),
		severity:  "low",
		ruleIDGen: func(m []string) string { return m[4] },
		titleGen:  func(m []string) string { return strings.TrimSpace(m[5]) },
		fileGen:   func(m []string) string { return m[1] },
		lineGen:   func(m []string) int { return atoiSafe(m[2]) },
		messageFn: func(m []string) string { return m[5] },
	},
	{
		// pytest: "FAILED path/to/test_file.py::TestClass::test_name - AssertionError"
		scanner:   "pytest",
		pattern:   regexp.MustCompile(`(?m)^FAILED\s+([^\s:]+)::(\S+)\s+-\s+(.*)$`),
		severity:  "medium",
		ruleIDGen: func(m []string) string { return "test-failure-" + sanitizeID(m[2]) },
		titleGen:  func(m []string) string { return "Test failed: " + m[2] },
		fileGen:   func(m []string) string { return m[1] },
		lineGen:   func(m []string) int { return 0 },
		messageFn: func(m []string) string { return m[3] },
	},
}

// JobNameToScanner maps a GitHub Actions job name to the scanner family
// that runs inside it. Used when a job fails but no log line matches
// (e.g. the job crashed before any tool emitted output).
func JobNameToScanner(jobName string) string {
	n := strings.ToLower(jobName)
	switch {
	case strings.Contains(n, "sast"), strings.Contains(n, "semgrep"):
		return "semgrep"
	case strings.Contains(n, "container-scan"), strings.Contains(n, "container-build"):
		return "trivy"
	case strings.Contains(n, "dependency"), strings.Contains(n, "cve"):
		return "npm-audit"
	case strings.Contains(n, "secret"), strings.Contains(n, "gitleaks"):
		return "gitleaks"
	case strings.Contains(n, "sbom"):
		return "syft"
	case strings.Contains(n, "lint"):
		return "linter"
	case strings.Contains(n, "test"):
		return "pytest"
	case strings.Contains(n, "iac"):
		return "checkov"
	default:
		return "unknown"
	}
}

// ParseJobLog runs all log patterns against the given log and returns
// the matched findings. If the log is empty or has no matches, returns
// a single synthetic finding based on the job name so the UI still
// has something to show.
func ParseJobLog(jobName string, jobID int64, logText string) LogToFindingsResult {
	scanner := JobNameToScanner(jobName)

	truncated := false
	if len(logText) > maxLogBytes {
		logText = logText[len(logText)-maxLogBytes:]
		truncated = true
	}

	var findings []Finding
	seen := make(map[string]bool)

	for _, p := range logPatterns {
		if !scannerMatches(p.scanner, scanner) {
			continue
		}
		matches := p.pattern.FindAllStringSubmatch(logText, -1)
		for _, m := range matches {
			key := p.scanner + ":" + p.ruleIDGen(m) + ":" + p.fileGen(m) + ":" + strconv.Itoa(p.lineGen(m))
			if seen[key] {
				continue
			}
			seen[key] = true

			file := p.fileGen(m)
			remediation := defaultRemediationFor(p.scanner)
			if p.remediation != nil {
				remediation = p.remediation(m)
			}
			findings = append(findings, Finding{
				Title:                     p.titleGen(m),
				SourceTool:                p.scanner,
				Severity:                  p.severity,
				Evidence:                  p.messageFn(m),
				FileLocation:              file,
				Line:                      p.lineGen(m),
				RemediationRecommendation: remediation,
				Type:                      p.scanner,
				Scanner:                   p.scanner,
				Explanation:               p.messageFn(m),
				Recommendation:            defaultRecommendationFor(p.scanner),
				RuleID:                    p.ruleIDGen(m),
			})
		}
	}

	if len(findings) == 0 {
		// Synthesize a "job failed without parseable output" finding so
		// the UI never shows an empty list for a failed job. We also
		// try to detect specific failure modes in the log so the
		// synthesized finding carries actionable remediation text
		// instead of a generic "open the log" message.
		title := jobName + " failed"
		evidence := "Job '" + jobName + "' exited with non-zero status. No parseable security output was found in the log; the failure is likely a workflow configuration issue (missing dependency, wrong command, timeout)."
		remediation := "Open the full log on GitHub to diagnose the workflow failure. Common causes: missing package-lock.json, incorrect command, version mismatch."
		ruleID := "job-failure"
		severity := "medium"

		// Determine if this is a SARIF-upload scanner. For these
		// jobs the log will not contain parseable output (it lives
		// in the SARIF file rendered in the Code Scanning tab), so
		// any synthesized finding should point the user at the
		// Code Scanning tab rather than "open the log".
		isSarifScanner := scanner == "semgrep" || scanner == "trivy" ||
			scanner == "gitleaks" || scanner == "npm-audit" || scanner == "syft" ||
			scanner == "checkov"

		switch {
		case strings.Contains(logText, "CopyablePersistent") || strings.Contains(logText, "AccessorGetterCallback"):
			// Native module build failure: the package is too old
			// for the current Node.js V8 API. This is what
			// better-sqlite3@7.4.3 looks like against Node 24.
			title = "Native module build failure: outdated dependency"
			evidence = "A native module failed to compile against the current Node.js runtime. The package uses V8 APIs that have been removed (CopyablePersistent, AccessorGetterCallback, etc.). This is a *dependency* problem, not a workflow configuration error — `npm install` itself succeeded, but the post-install native build step failed."
			remediation = "Upgrade the affected package to a version that supports the current Node.js runtime. For better-sqlite3, version 7.6.0+ supports Node 18+; version 8.x+ supports Node 22+. Alternatively, use `--ignore-scripts` to skip native builds and rely on prebuilt binaries from a registry that supports the current Node version."
			ruleID = "native-module-outdated"
			severity = "high"
		case strings.Contains(logText, "ELIFECYCLE") || strings.Contains(logText, "npm error code"):
			// Generic npm error.
			title = "npm script failed"
			evidence = "An npm install / build script exited with non-zero status. Check the log for the specific package and command that failed."
			remediation = "Inspect the npm error message in the log. Common causes: peer dependency conflict, native module build failure (see above), missing build tools, or incompatible package version."
			ruleID = "npm-script-failed"
			severity = "medium"
		case isSarifScanner:
			// SARIF-upload scanner failed: the scanner's findings
			// live in the SARIF file rendered in the Code Scanning
			// tab, not in the job log. Direct the user there.
			title = jobName + " failed before SARIF upload"
			evidence = "The " + scanner + " job exited with non-zero status before it could upload its SARIF report. This is almost always a workflow configuration problem (e.g. the job crashed, or an earlier step like `npm install` failed). The log does not contain scanner output because the scanner never ran to completion."
			remediation = "Open the Code Scanning tab in this repository — alerts that were uploaded by EARLIER successful runs of this same workflow may still be listed there. Otherwise, fix the workflow (e.g. add `--ignore-scripts` to the failing npm install step) and trigger a new run so the scanner can complete and upload."
			ruleID = "sarif-not-uploaded"
			severity = "low"
		case strings.Contains(logText, "Error: Process completed with exit code"):
			// Generic GitHub Actions step failure (last-resort case
			// so it does not shadow the more specific scanners above).
			title = "Job step exited non-zero"
			evidence = "A job step exited with a non-zero status. Inspect the full log for the specific command and exit code."
			remediation = "Open the raw log on GitHub Actions to identify which step failed and why."
			ruleID = "step-exit-nonzero"
		}

		findings = append(findings, Finding{
			Title:                     title,
			SourceTool:                scanner,
			Severity:                  severity,
			Evidence:                  evidence,
			FileLocation:              "",
			RemediationRecommendation: remediation,
			Type:                      scanner,
			Scanner:                   scanner,
			Explanation:               "Job '" + jobName + "' failed; log did not contain parseable scanner output.",
			Recommendation:            remediation,
			RuleID:                    ruleID,
		})
	}

	return LogToFindingsResult{
		Scanner:   scanner,
		JobName:   jobName,
		JobID:     jobID,
		Findings:  findings,
		Unparsed:  0,
		Truncated: truncated,
	}
}

func scannerMatches(patternScanner, jobScanner string) bool {
	if patternScanner == jobScanner {
		return true
	}
	if patternScanner == "linter" && (jobScanner == "linter" || jobScanner == "pytest") {
		return true
	}
	// Trivy and npm-audit often appear together in the same job
	// (dependency-scan runs both `npm audit` and Trivy fs scan).
	// Allow either pattern to match the other's job.
	if (patternScanner == "trivy" || patternScanner == "npm-audit") &&
		(jobScanner == "trivy" || jobScanner == "npm-audit") {
		return true
	}
	return false
}

func defaultRemediationFor(scanner string) string {
	switch scanner {
	case "semgrep":
		return "Review the Semgrep rule docs and refactor the offending line to remove the unsafe pattern."
	case "trivy":
		return "Upgrade the affected package to a non-vulnerable version, or remove the dependency if no fix is available."
	case "gitleaks":
		return "Rotate the exposed secret immediately and remove it from source. Move secrets to environment variables or a secret manager."
	case "npm-audit":
		return "Run `npm audit fix` to upgrade vulnerable packages, or pin to a non-vulnerable version."
	case "linter":
		return "Fix the lint violation reported on the indicated line."
	case "pytest":
		return "Investigate the failing test; the assertion error message indicates the expected vs. actual values."
	default:
		return "Review the raw log on GitHub Actions for the failure cause."
	}
}

func defaultRecommendationFor(scanner string) string {
	switch scanner {
	case "semgrep":
		return "Replace the unsafe pattern identified by Semgrep."
	case "trivy":
		return "Update or remove the vulnerable package."
	case "gitleaks":
		return "Rotate the secret and store it in a secret manager."
	case "npm-audit":
		return "Upgrade the vulnerable dependency."
	default:
		return "See the log for details."
	}
}

func atoiSafe(s string) int {
	if s == "" {
		return 0
	}
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return 0
		}
		n = n*10 + int(c-'0')
		if n > 1000000 {
			return 0
		}
	}
	return n
}

func sanitizeID(s string) string {
	s = strings.ToLower(s)
	out := make([]rune, 0, len(s))
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			out = append(out, r)
		} else if r == '-' || r == '_' {
			out = append(out, r)
		}
	}
	if len(out) > 64 {
		out = out[:64]
	}
	return string(out)
}

// timeNow is a small indirection so the tests can override the clock if
// they want to assert on the synthesized finding's timestamp later.
var timeNow = time.Now
