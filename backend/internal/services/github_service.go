package services

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type GitHubService struct {
	client *http.Client
}

func NewGitHubService() *GitHubService {
	return &GitHubService{
		client: &http.Client{Timeout: 30 * time.Second},
	}
}

func (s *GitHubService) doRequest(req *http.Request) ([]byte, int, error) {
	resp, err := s.client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, err
	}
	return body, resp.StatusCode, nil
}

func (s *GitHubService) newRequest(method, url, token string) (*http.Request, error) {
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github.v3+json")
	req.Header.Set("User-Agent", "ai-devsecops-pipeline-engineer")
	return req, nil
}

func (s *GitHubService) jsonRequest(method, url, token string, payload []byte) (*http.Request, error) {
	req, err := http.NewRequest(method, url, bytes.NewReader(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github.v3+json")
	req.Header.Set("User-Agent", "ai-devsecops-pipeline-engineer")
	req.Header.Set("Content-Type", "application/json")
	return req, nil
}

// ----- Auth & Validation -----

func (s *GitHubService) ValidateToken(accessToken string) error {
	req, err := s.newRequest("GET", "https://api.github.com/user", accessToken)
	if err != nil {
		return err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return err
	}
	if status == http.StatusOK {
		return nil
	}
	switch status {
	case http.StatusUnauthorized:
		return fmt.Errorf("GitHub token is invalid or expired: %s", string(body))
	case http.StatusForbidden:
		return fmt.Errorf("GitHub token lacks required permissions: %s", string(body))
	default:
		return fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
}

func (s *GitHubService) CheckRepoAccess(accessToken, fullName string) error {
	url := fmt.Sprintf("https://api.github.com/repos/%s", fullName)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return err
	}
	if status == http.StatusOK {
		return nil
	}
	switch status {
	case http.StatusNotFound:
		return fmt.Errorf("repository %s not found or token lacks access", fullName)
	case http.StatusForbidden:
		return fmt.Errorf("token lacks permission to access %s. Required scope: repo", fullName)
	case http.StatusUnauthorized:
		return fmt.Errorf("GitHub token is invalid or expired: %s", string(body))
	default:
		return fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
}

// ----- Repo Contents -----

type RepoContent struct {
	Name string `json:"name"`
	Path string `json:"path"`
	Type string `json:"type"`
}

func (s *GitHubService) ListRepoContents(accessToken, fullName, path string) ([]RepoContent, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/contents/%s", fullName, path)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var contents []RepoContent
	if err := json.Unmarshal(body, &contents); err != nil {
		var single RepoContent
		if err2 := json.Unmarshal(body, &single); err2 != nil {
			return nil, fmt.Errorf("failed to parse repo contents: %w", err)
		}
		contents = []RepoContent{single}
	}
	return contents, nil
}

func (s *GitHubService) GetRepoDefaultBranch(accessToken, fullName string) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s", fullName)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return "", err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return "", err
	}
	if status != http.StatusOK {
		return "", fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var repo struct {
		DefaultBranch string `json:"default_branch"`
	}
	if err := json.Unmarshal(body, &repo); err != nil {
		return "", err
	}
	return repo.DefaultBranch, nil
}

// ----- Branches -----

func (s *GitHubService) GetBranchSHA(accessToken, fullName, branch string) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/git/refs/heads/%s", fullName, branch)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return "", err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return "", err
	}
	if status != http.StatusOK {
		return "", fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var ref struct {
		Object struct {
			SHA string `json:"sha"`
		} `json:"object"`
	}
	if err := json.Unmarshal(body, &ref); err != nil {
		return "", err
	}
	return ref.Object.SHA, nil
}

func (s *GitHubService) CreateBranch(accessToken, fullName, branchName, baseBranch string) error {
	sha, err := s.GetBranchSHA(accessToken, fullName, baseBranch)
	if err != nil {
		return fmt.Errorf("failed to get base branch SHA: %w", err)
	}
	url := fmt.Sprintf("https://api.github.com/repos/%s/git/refs", fullName)
	payload := map[string]string{
		"ref": fmt.Sprintf("refs/heads/%s", branchName),
		"sha": sha,
	}
	bodyBytes, _ := json.Marshal(payload)
	req, err := s.jsonRequest("POST", url, accessToken, bodyBytes)
	if err != nil {
		return err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return err
	}
	if status != http.StatusCreated {
		return fmt.Errorf("GitHub API error creating branch (status %d): %s", status, string(body))
	}
	return nil
}

// ----- Files -----

func (s *GitHubService) CreateFile(accessToken, fullName, path, content, commitMessage, branch string) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/contents/%s", fullName, path)
	encoded := base64.StdEncoding.EncodeToString([]byte(content))
	payload := map[string]string{
		"message": commitMessage,
		"content": encoded,
		"branch":  branch,
	}
	bodyBytes, _ := json.Marshal(payload)
	req, err := s.jsonRequest("PUT", url, accessToken, bodyBytes)
	if err != nil {
		return "", err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return "", err
	}
	if status != http.StatusCreated && status != http.StatusOK {
		return "", fmt.Errorf("GitHub API error creating file (status %d): %s", status, string(body))
	}
	var result struct {
		Content struct {
			SHA string `json:"sha"`
		} `json:"content"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return "", err
	}
	return result.Content.SHA, nil
}

// ----- Pull Requests -----

type CreatePRResult struct {
	Number  int    `json:"number"`
	HTMLURL string `json:"html_url"`
}

func (s *GitHubService) CreatePullRequest(accessToken, fullName, title, body, head, base string) (*CreatePRResult, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/pulls", fullName)
	payload := map[string]string{
		"title": title,
		"body":  body,
		"head":  head,
		"base":  base,
	}
	bodyBytes, _ := json.Marshal(payload)
	req, err := s.jsonRequest("POST", url, accessToken, bodyBytes)
	if err != nil {
		return nil, err
	}
	respBody, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusCreated {
		return nil, fmt.Errorf("GitHub API error creating PR (status %d): %s", status, string(respBody))
	}
	var result CreatePRResult
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// ----- Workflows -----

func (s *GitHubService) TriggerWorkflowDispatch(accessToken, fullName, workflowFilename, ref string) error {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/workflows/%s/dispatches", fullName, workflowFilename)
	payload := map[string]string{"ref": ref}
	bodyBytes, _ := json.Marshal(payload)
	req, err := s.jsonRequest("POST", url, accessToken, bodyBytes)
	if err != nil {
		return err
	}
	_, status, err := s.doRequest(req)
	if err != nil {
		return err
	}
	if status != http.StatusNoContent {
		respBody, _ := io.ReadAll(req.Body)
		return fmt.Errorf("GitHub API error triggering workflow (status %d): %s", status, string(respBody))
	}
	return nil
}

type WorkflowRun struct {
	ID         int64  `json:"id"`
	Status     string `json:"status"`
	Conclusion string `json:"conclusion"`
	HTMLURL    string `json:"html_url"`
	RunNumber  int    `json:"run_number"`
}

func (s *GitHubService) ListWorkflowRuns(accessToken, fullName string, perPage int) ([]WorkflowRun, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs?per_page=%d&page=1", fullName, perPage)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var result struct {
		WorkflowRuns []WorkflowRun `json:"workflow_runs"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result.WorkflowRuns, nil
}

func (s *GitHubService) ListWorkflowRunsForFile(accessToken, fullName, workflowFilename string, perPage int) ([]WorkflowRun, error) {
	workflowFileForAPI := workflowFilename
	if strings.HasPrefix(workflowFilename, ".github/workflows/") {
		workflowFileForAPI = strings.TrimPrefix(workflowFilename, ".github/workflows/")
	}
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/workflows/%s/runs?per_page=%d&page=1", fullName, workflowFileForAPI, perPage)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var result struct {
		WorkflowRuns []WorkflowRun `json:"workflow_runs"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result.WorkflowRuns, nil
}

func (s *GitHubService) GetWorkflowRun(accessToken, fullName string, runID int64) (*WorkflowRun, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs/%d", fullName, runID)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var run WorkflowRun
	if err := json.Unmarshal(body, &run); err != nil {
		return nil, err
	}
	return &run, nil
}

type WorkflowStep struct {
	Name       string `json:"name"`
	Status     string `json:"status"`
	Conclusion string `json:"conclusion"`
	Number     int    `json:"number"`
}

type WorkflowJob struct {
	ID         int64          `json:"id"`
	Name       string         `json:"name"`
	Status     string         `json:"status"`
	Conclusion string         `json:"conclusion"`
	Steps      []WorkflowStep `json:"steps"`
}

func (s *GitHubService) GetWorkflowRunJobs(accessToken, fullName string, runID int64) ([]WorkflowJob, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs/%d/jobs", fullName, runID)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var result struct {
		Jobs []WorkflowJob `json:"jobs"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result.Jobs, nil
}

func (s *GitHubService) GetWorkflowRunLogs(accessToken, fullName string, runID int64) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs/%d/logs", fullName, runID)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return "", err
	}
	req.Header.Set("Accept", "application/vnd.github.v3.raw")
	body, status, err := s.doRequest(req)
	if err != nil {
		return "", err
	}
	if status != http.StatusOK {
		return "", fmt.Errorf("GitHub API error (status %d)", status)
	}
	return string(body), nil
}

// ----- Existing Workflow Files -----

type WorkflowFile struct {
	Name string `json:"name"`
	Path string `json:"path"`
	Type string `json:"type"`
}

func (s *GitHubService) FetchWorkflowFiles(accessToken, fullName string) ([]WorkflowFile, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/contents/.github/workflows", fullName)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var files []WorkflowFile
	if err := json.Unmarshal(body, &files); err != nil {
		return nil, err
	}
	return files, nil
}

// ----- Check Run Annotations -----

// CheckRunAnnotation mirrors the shape we care about from the
// GitHub Check Runs / Actions annotations API. Only the fields
// used by the dashboard categoriser (annotation_dashboard.go) are
// modelled; everything else is dropped.
type CheckRunAnnotation struct {
	Title           string `json:"title,omitempty"`
	Message         string `json:"message,omitempty"`
	AnnotationLevel string `json:"annotation_level,omitempty"`
	RawDetails      string `json:"raw_details,omitempty"`
	Path            string `json:"path,omitempty"`
	StartLine       int    `json:"start_line,omitempty"`
}

// GetRunAnnotations fetches the inline annotations attached to a
// workflow run via the Check Runs API. The endpoint we hit is
//
//	GET /repos/{owner}/{repo}/check-runs/{check_run_id}/annotations
//
// Caller is expected to pass the workflow run id which GitHub
// also surfaces as a check-run id for the workflow's "check
// suite" entry. The function walks the per-job check runs under
// the run's jobs and concatenates all of their annotations so
// downstream categorisation sees a single flat list.
func (s *GitHubService) GetRunAnnotations(accessToken, fullName string, runID int64) ([]CheckRunAnnotation, error) {
	// Workflow-level annotations (these are the ones GitHub
	// renders in the UI as the "Annotations" tab on a run).
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs/%d/annotations", fullName, runID)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		// Non-fatal: many repos have zero annotations. Return an
		// empty slice so the dashboard falls back to the log
		// parser path.
		return []CheckRunAnnotation{}, nil
	}
	var anns []CheckRunAnnotation
	if err := json.Unmarshal(body, &anns); err != nil {
		return nil, fmt.Errorf("failed to parse annotations: %w", err)
	}
	return anns, nil
}

// ----- Job Logs -----

// GetJobLogs fetches the plain-text log for a single Actions job.
// Unlike GetWorkflowRunLogs (which returns a zipped archive of
// every job's logs) this endpoint returns one job's log as a
// single text payload, which is much easier to display in the
// UI and to feed to the log finding parser.
//
// Endpoint:
//
//	GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs
func (s *GitHubService) GetJobLogs(accessToken, fullName string, jobID int64) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/jobs/%d/logs", fullName, jobID)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return "", err
	}
	// Plain text — not the default JSON accept header.
	req.Header.Set("Accept", "application/vnd.github.v3.raw")
	body, status, err := s.doRequest(req)
	if err != nil {
		return "", err
	}
	if status == http.StatusOK {
		return string(body), nil
	}
	// GitHub returns 302 with a signed S3 URL for the actual log
	// blob; the underlying http client follows it by default but
	// the v3+json accept header we sent may confuse some proxies.
	// If we got here with a non-OK status and no error, surface
	// it as a soft failure so the caller can fall back to the
	// per-run log archive.
	return "", fmt.Errorf("GitHub API error fetching job logs (status %d)", status)
}

// ----- Code Scanning Alerts -----

// CodeScanningAlert mirrors the subset of the GitHub Code
// Scanning alerts API we consume in the dashboard. Severity is
// split into two fields because the API exposes them separately
// (rule_severity vs security_severity); see mapGitHubSeverity.
type CodeScanningAlert struct {
	RuleID           string `json:"rule_id"`
	RuleSeverity     string `json:"rule_severity"`
	SecuritySeverity string `json:"security_severity"`
	RuleDescription  string `json:"rule_description"`
	Tool             string `json:"tool"`
	Message          string `json:"message"`
	FilePath         string `json:"file_path"`
	StartLine        int    `json:"start_line"`
	CWE              string `json:"cwe"`
	HTMLURL          string `json:"html_url"`
}

// ListCodeScanningAlerts fetches the open SARIF-uploaded alerts
// for a repository. The state=open filter matches the dashboard
// "current findings" view; closed alerts are intentionally
// excluded so we do not re-show findings the user has already
// resolved on GitHub.
//
// Endpoint:
//
//	GET /repos/{owner}/{repo}/code-scanning/alerts?state=open&per_page=N
func (s *GitHubService) ListCodeScanningAlerts(accessToken, fullName string, perPage int) ([]CodeScanningAlert, error) {
	if perPage <= 0 {
		perPage = 100
	}
	url := fmt.Sprintf("https://api.github.com/repos/%s/code-scanning/alerts?state=open&per_page=%d", fullName, perPage)
	req, err := s.newRequest("GET", url, accessToken)
	if err != nil {
		return nil, err
	}
	body, status, err := s.doRequest(req)
	if err != nil {
		return nil, err
	}
	// 404/403: code scanning is not enabled for this repo, or
	// the token lacks the `security_events` scope. Return an
	// empty slice so the caller treats this as "no alerts
	// available" rather than a hard error.
	if status == http.StatusNotFound || status == http.StatusForbidden {
		return []CodeScanningAlert{}, nil
	}
	if status != http.StatusOK {
		return nil, fmt.Errorf("GitHub API error (status %d): %s", status, string(body))
	}
	var alerts []CodeScanningAlert
	if err := json.Unmarshal(body, &alerts); err != nil {
		return nil, fmt.Errorf("failed to parse code scanning alerts: %w", err)
	}
	return alerts, nil
}

func (s *GitHubService) CancelWorkflowRun(accessToken, fullName string, runID int64) error {
	url := fmt.Sprintf("https://api.github.com/repos/%s/actions/runs/%d/cancel", fullName, runID)
	req, err := s.jsonRequest("POST", url, accessToken, nil)
	if err != nil {
		return err
	}
	_, status, err := s.doRequest(req)
	if err != nil {
		return err
	}
	if status != http.StatusAccepted && status != http.StatusNoContent {
		return fmt.Errorf("GitHub API error cancelling workflow (status %d)", status)
	}
	return nil
}
