package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type AIService struct {
	baseURL string
	client  *http.Client
}

func NewAIService(baseURL string) *AIService {
	return &AIService{
		baseURL: baseURL,
		client:  &http.Client{Timeout: 600 * time.Second},
	}
}

type GenerateRequest struct {
	RepositoryID         string         `json:"repository_id"`
	RepositoryFullName   string         `json:"repository_full_name"`
	GitHubToken          string         `json:"github_token"`
	ProjectID            string         `json:"project_id"`
	Query                string         `json:"query"`
	Language             string         `json:"language"`
	Framework            string         `json:"framework"`
	DeployTarget         string         `json:"deploy_target"`
	ProjectType          string         `json:"project_type"`
	SecurityRequirements []string       `json:"security_requirements"`
	CachedInsights       map[string]any `json:"cached_insights"`
}

type GenerateResponse struct {
	GeneratedWorkflow  string   `json:"generated_workflow"`
	GeneratedStages    []string `json:"generated_stages"`
	Explanation        string   `json:"explanation"`
	ValidationPassed   bool     `json:"validation_passed"`
	ValidationErrors   []string `json:"validation_errors"`
	ValidationWarnings []string `json:"validation_warnings"`
	GitHubBranch       string   `json:"github_branch"`
	GitHubPRNumber     int      `json:"github_pr_number"`
	GitHubPRURL        string   `json:"github_pr_url"`
	WorkflowRunID      int      `json:"workflow_run_id"`
	WorkflowStatus     string   `json:"workflow_status"`
	WorkflowConclusion string   `json:"workflow_conclusion"`
	RiskScore          float64  `json:"risk_score"`
	ComplianceScore    float64  `json:"compliance_score"`
	Findings           []any    `json:"findings"`
	Summary            string   `json:"summary"`
	Errors             []string `json:"errors"`
	WorkflowFile       string   `json:"workflow_file"`
	// NodeIO is the per-node I/O trace for every node in Tahap 1-3
	// that ran during generation. Each entry has the shape:
	//   { node, phase, started_at, status, duration_ms,
	//     input_keys, output_summary, error? }
	// Mirrors `state["node_io"]` from the AI service, which is
	// already populated by `_invoke_graph_phase` for every node.
	NodeIO []map[string]any `json:"node_io"`
}

func (s *AIService) Generate(req GenerateRequest) (*GenerateResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", s.baseURL+"/api/pipeline/generate", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to call AI service: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result GenerateResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse AI service response: %w", err)
	}

	return &result, nil
}

type AnalyzeRequest struct {
	RepositoryID string `json:"repository_id"`
	GitHubToken  string `json:"github_token"`
	ProjectID    string `json:"project_id"`
}

type AnalyzeResponse struct {
	Technologies      map[string]any `json:"technologies"`
	Architecture      any            `json:"architecture"`
	SecurityNeeds     map[string]any `json:"security_requirements"`
	ExistingWorkflows []string       `json:"existing_workflows"`
	Deployment        map[string]any `json:"deployment"`
	Errors            []string       `json:"errors"`
}

func (s *AIService) AnalyzeRepository(req AnalyzeRequest) (*AnalyzeResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", s.baseURL+"/api/pipeline/repo/analyze", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to call AI service: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result AnalyzeResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse AI service response: %w", err)
	}

	return &result, nil
}

type DeployRequest struct {
	RepositoryID string `json:"repository_id"`
	GitHubToken  string `json:"github_token"`
	WorkflowYAML string `json:"workflow_yaml"`
	WorkflowFile string `json:"workflow_filename"`
}

type DeployResponse struct {
	Branch       string   `json:"branch"`
	CommitSHA    string   `json:"commit_sha"`
	PRNumber     int      `json:"pr_number"`
	PRURL        string   `json:"pr_url"`
	Success      bool     `json:"success"`
	Errors       []string `json:"errors"`
	WorkflowFile string   `json:"workflow_file"`
}

func (s *AIService) Deploy(req DeployRequest) (*DeployResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", s.baseURL+"/api/pipeline/deploy", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to call AI service: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result DeployResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse AI service response: %w", err)
	}

	return &result, nil
}

type ValidateRequest struct {
	RepositoryFullName string `json:"repository_full_name"`
	WorkflowYAML       string `json:"workflow_yaml"`
}

type ValidateResponse struct {
	Valid                 bool     `json:"valid"`
	SyntaxOK              bool     `json:"syntax_ok"`
	ActionsPinned         bool     `json:"actions_pinned"`
	PermissionsMinimal    bool     `json:"permissions_minimal"`
	MissingSecurityStages []string `json:"missing_security_stages"`
	Errors                []string `json:"errors"`
	Warnings              []string `json:"warnings"`
}

func (s *AIService) Validate(req ValidateRequest) (*ValidateResponse, error) {
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	httpReq, err := http.NewRequest("POST", s.baseURL+"/api/pipeline/validate", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to call AI service: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result ValidateResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse AI service response: %w", err)
	}

	return &result, nil
}

type PipelineAnalysisResponse struct {
	Summary               string         `json:"summary"`
	Findings              []any          `json:"findings"`
	RiskScore             float64        `json:"risk_score"`
	RiskLevel             string         `json:"risk_level"`
	SecurityPosture       float64        `json:"security_posture"`
	SecurityCoverageScore float64        `json:"security_coverage_score"`
	ComplianceScore       float64        `json:"compliance_score"`
	ComplianceMappings    []any          `json:"compliance_mappings"`
	SeverityBreakdown     map[string]int `json:"severity_breakdown"`
	Recommendations       []any          `json:"recommendations"`
	Errors                []string       `json:"errors"`
	ValidationFindings    []any          `json:"validation_findings"`
	DashboardFindings     map[string]any `json:"dashboard_findings"`
}

func (s *AIService) AnalyzeExecution(repoID string, runID int, token string) (*PipelineAnalysisResponse, error) {
	body, _ := json.Marshal(map[string]interface{}{
		"repository_id": repoID,
		"github_token":  token,
	})

	httpReq, err := http.NewRequest("POST", fmt.Sprintf("%s/api/pipeline/analyze/%d", s.baseURL, runID), bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to call AI service: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("AI service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result PipelineAnalysisResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse AI service response: %w", err)
	}

	return &result, nil
}
