package handlers

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/config"
	"github.com/user/ai-devsecops-backend/internal/models"
	"github.com/user/ai-devsecops-backend/internal/repositories"
	"github.com/user/ai-devsecops-backend/internal/services"
	"github.com/user/ai-devsecops-backend/internal/utils"
	"gorm.io/gorm"
)

type PipelineHandler struct {
	pipelineRepo repositories.PipelineRepository
	runRepo      repositories.PipelineRunRepository
	analysisRepo repositories.PipelineAnalysisRepository
	insightRepo  repositories.RepositoryInsightRepository
	db           *gorm.DB
	cfg          *config.Config
	aiService    *services.AIService
}

func NewPipelineHandler(
	pipelineRepo repositories.PipelineRepository,
	runRepo repositories.PipelineRunRepository,
	analysisRepo repositories.PipelineAnalysisRepository,
	insightRepo repositories.RepositoryInsightRepository,
	db *gorm.DB,
	cfg *config.Config,
	aiService *services.AIService,
) *PipelineHandler {
	return &PipelineHandler{
		pipelineRepo: pipelineRepo,
		runRepo:      runRepo,
		analysisRepo: analysisRepo,
		insightRepo:  insightRepo,
		db:           db,
		cfg:          cfg,
		aiService:    aiService,
	}
}

// GET /api/v1/repositories/:repoId/pipelines
func (h *PipelineHandler) ListByRepository(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	pipelines, err := h.pipelineRepo.FindByRepository(repoID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"pipelines": pipelines})
}

// GET /api/v1/pipelines (global list with pagination)
func (h *PipelineHandler) ListAll(c *gin.Context) {
	userIDStr, _ := c.Get("userID")
	userID, err := uuid.Parse(userIDStr.(string))
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user"})
		return
	}

	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	sortBy := c.DefaultQuery("sort_by", "created_at")
	sortOrder := c.DefaultQuery("sort_order", "desc")

	if page < 1 {
		page = 1
	}
	if limit < 1 || limit > 100 {
		limit = 20
	}

	pipelines, total, err := h.pipelineRepo.ListAll(userID, page, limit, sortBy, sortOrder)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"pipelines": pipelines,
		"total":     total,
		"page":      page,
		"limit":     limit,
	})
}

// GET /api/v1/pipelines/:pipelineId
func (h *PipelineHandler) GetByID(c *gin.Context) {
	pipelineID, err := uuid.Parse(c.Param("pipelineId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid pipeline id"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByID(pipelineID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "pipeline not found"})
		return
	}

	c.JSON(http.StatusOK, pipeline)
}

// DELETE /api/v1/pipelines/:pipelineId
func (h *PipelineHandler) Delete(c *gin.Context) {
	pipelineID, err := uuid.Parse(c.Param("pipelineId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid pipeline id"})
		return
	}

	if err := h.pipelineRepo.Delete(pipelineID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "pipeline deleted"})
}

// GET /api/v1/repositories/:repoId/pipelines/:version
func (h *PipelineHandler) GetByVersion(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	version, err := strconv.Atoi(c.Param("version"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid version number"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByRepositoryAndVersion(repoID, version)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "pipeline version not found"})
		return
	}

	c.JSON(http.StatusOK, pipeline)
}

// POST /api/v1/pipelines/compare
type compareRequest struct {
	PipelineAID uuid.UUID `json:"pipeline_a_id" binding:"required"`
	PipelineBID uuid.UUID `json:"pipeline_b_id" binding:"required"`
}

func (h *PipelineHandler) Compare(c *gin.Context) {
	var req compareRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	pipelineA, err := h.pipelineRepo.FindByID(req.PipelineAID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "pipeline A not found"})
		return
	}

	pipelineB, err := h.pipelineRepo.FindByID(req.PipelineBID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "pipeline B not found"})
		return
	}

	runsA, _ := h.runRepo.FindByPipeline(pipelineA.ID)
	runsB, _ := h.runRepo.FindByPipeline(pipelineB.ID)

	var analysisA, analysisB *models.PipelineAnalysis
	if len(runsA) > 0 {
		analysisA, _ = h.analysisRepo.FindByRunID(latestCompletedRun(runsA).ID)
	}
	if len(runsB) > 0 {
		analysisB, _ = h.analysisRepo.FindByRunID(latestCompletedRun(runsB).ID)
	}

	successRateA := calcSuccessRate(runsA)
	successRateB := calcSuccessRate(runsB)

	var riskScoreA, riskScoreB float64
	var complianceScoreA, complianceScoreB float64
	var coverageScoreA, coverageScoreB float64

	if analysisA != nil {
		riskScoreA = analysisA.RiskScore
		complianceScoreA = analysisA.ComplianceScore
		coverageScoreA = analysisA.SecurityCoverageScore
	}
	if analysisB != nil {
		riskScoreB = analysisB.RiskScore
		complianceScoreB = analysisB.ComplianceScore
		coverageScoreB = analysisB.SecurityCoverageScore
	}

	c.JSON(http.StatusOK, gin.H{
		"pipeline_a": gin.H{
			"version":                pipelineA.VersionNumber,
			"status":                 pipelineA.Status,
			"created_at":             pipelineA.CreatedAt,
			"stages":                 pipelineA.Stages,
			"security_controls":      pipelineA.SecurityControlsApplied,
			"risk_score":             riskScoreA,
			"compliance_score":       complianceScoreA,
			"security_coverage":      coverageScoreA,
			"run_count":              len(runsA),
			"execution_success_rate": successRateA,
		},
		"pipeline_b": gin.H{
			"version":                pipelineB.VersionNumber,
			"status":                 pipelineB.Status,
			"created_at":             pipelineB.CreatedAt,
			"stages":                 pipelineB.Stages,
			"security_controls":      pipelineB.SecurityControlsApplied,
			"risk_score":             riskScoreB,
			"compliance_score":       complianceScoreB,
			"security_coverage":      coverageScoreB,
			"run_count":              len(runsB),
			"execution_success_rate": successRateB,
		},
		"deltas": gin.H{
			"risk_score":             delta(riskScoreB, riskScoreA, false),
			"compliance_score":       delta(complianceScoreB, complianceScoreA, true),
			"security_coverage":      delta(coverageScoreB, coverageScoreA, true),
			"execution_success_rate": delta(successRateB, successRateA, true),
		},
	})
}

// GET /api/v1/repositories/:repoId/pipelines/:version/runs
func (h *PipelineHandler) ListRuns(c *gin.Context) {
	pipelineID, err := uuid.Parse(c.Param("pipelineId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid pipeline id"})
		return
	}

	runs, err := h.runRepo.FindByPipeline(pipelineID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"runs": runs})
}

// POST /api/v1/repositories/:repoId/pipelines/:version/sync-runs
func (h *PipelineHandler) SyncRuns(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repo id"})
		return
	}
	versionStr := c.Param("version")
	version, err := strconv.Atoi(versionStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid version"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByRepositoryAndVersion(repoID, version)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "pipeline not found"})
		return
	}

	repo := pipeline.Repository
	if repo.AccessTokenEncrypted == "" || repo.FullName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repository has no GitHub token"})
		return
	}

	encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
	if len(encryptionKey) != 32 {
		fallback := make([]byte, 32)
		copy(fallback, "ai-devsecops-default-key-32bytes!")
		encryptionKey = fallback
	}
	decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey)
	if decryptErr != nil {
		fmt.Printf("[SyncRuns] ERROR: token decryption failed: %v\n", decryptErr)
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to decrypt token: %v", decryptErr)})
		return
	}

	svc := services.NewGitHubService()

	// Try multiple workflow file paths
	workflowFiles := []string{}
	if pipeline.DeploymentResults != "" && pipeline.DeploymentResults != "null" {
		var depInfo struct {
			WorkflowFile string `json:"workflow_file"`
		}
		if err := json.Unmarshal([]byte(pipeline.DeploymentResults), &depInfo); err == nil && depInfo.WorkflowFile != "" {
			workflowFiles = append(workflowFiles, depInfo.WorkflowFile)
		}
	}
	if pipeline.GeneratedYAML != "" {
		if matches := regexp.MustCompile(`path:\s*["']?\.github/workflows/([^"']+\.ya?ml)["']?`).FindStringSubmatch(pipeline.GeneratedYAML); len(matches) > 1 {
			wf := ".github/workflows/" + matches[1]
			if !contains(workflowFiles, wf) {
				workflowFiles = append(workflowFiles, wf)
			}
		}
		if matches := regexp.MustCompile(`["']?\.github/workflows/([^"']+\.ya?ml)["']?`).FindStringSubmatch(pipeline.GeneratedYAML); len(matches) > 1 {
			wf := ".github/workflows/" + matches[1]
			if !contains(workflowFiles, wf) {
				workflowFiles = append(workflowFiles, wf)
			}
		}
	}
	workflowFiles = append(workflowFiles, fmt.Sprintf(".github/workflows/ai-devsecops-v%d.yml", version))
	workflowFiles = append(workflowFiles, ".github/workflows/pr-pipeline.yml")
	workflowFiles = append(workflowFiles, ".github/workflows/ci-cd.yml")
	workflowFiles = append(workflowFiles, ".github/workflows/main.yml")
	workflowFiles = append(workflowFiles, ".github/workflows/deploy.yml")

	// Deduplicate
	seen := map[string]bool{}
	uniqueFiles := []string{}
	for _, f := range workflowFiles {
		if !seen[f] {
			seen[f] = true
			uniqueFiles = append(uniqueFiles, f)
		}
	}

	var ghRuns []services.WorkflowRun
	var usedWorkflowFile string
	var fileErrors []map[string]string

	// Validate the PAT up front. If it cannot authenticate against
	// GitHub at all, none of the ListWorkflowRunsForFile calls will
	// succeed and we should surface the auth error immediately instead
	// of trying every workflow file in turn.
	if err := svc.ValidateToken(decryptedToken); err != nil {
		c.JSON(http.StatusBadGateway, gin.H{
			"error":         fmt.Sprintf("GitHub token check failed: %v. Reconnect the repository to refresh the token.", err),
			"workflow_file": usedWorkflowFile,
			"synced":        []string{},
			"skipped":       []string{},
		})
		return
	}

	for _, wf := range uniqueFiles {
		fmt.Printf("[SyncRuns] Trying workflow file: %s\n", wf)
		runs, err := svc.ListWorkflowRunsForFile(decryptedToken, repo.FullName, wf, 10)
		if err != nil {
			fmt.Printf("[SyncRuns] Failed to fetch runs for '%s': %v\n", wf, err)
			fileErrors = append(fileErrors, map[string]string{
				"workflow_file": wf,
				"error":         err.Error(),
			})
			continue
		}
		if len(runs) > 0 {
			ghRuns = runs
			usedWorkflowFile = wf
			fmt.Printf("[SyncRuns] SUCCESS: found %d runs with workflow '%s'\n", len(runs), wf)
			break
		}
	}

	if len(ghRuns) == 0 {
		// If we had errors on every file, surface the first auth-related
		// error to the user; otherwise fall back to the existing
		// "no runs found" message.
		if len(fileErrors) > 0 && len(fileErrors) == len(uniqueFiles) {
			c.JSON(http.StatusBadGateway, gin.H{
				"error":         fmt.Sprintf("all %d workflow file probes failed. First error: %s", len(fileErrors), fileErrors[0]["error"]),
				"workflow_file": usedWorkflowFile,
				"synced":        []string{},
				"skipped":       []string{},
				"file_errors":   fileErrors,
			})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"message":       "sync complete - no runs found",
			"workflow_file": usedWorkflowFile,
			"synced":        []string{},
			"skipped":       []string{},
			"info":          fmt.Sprintf("no workflow runs found for workflow files: %v", uniqueFiles),
		})
		return
	}
	if usedWorkflowFile == "" {
		usedWorkflowFile = uniqueFiles[0]
	}

	fmt.Printf("[SyncRuns] Using workflow file: %s (%d runs)\n", usedWorkflowFile, len(ghRuns))

	// Build map of existing runs by GitHubRunID to avoid duplicates
	existingRuns := map[int64]*models.PipelineRun{}
	var existingList []models.PipelineRun
	h.db.Where("pipeline_id = ?", pipeline.ID).Find(&existingList)
	for i := range existingList {
		if existingList[i].GitHubRunID > 0 {
			existingRuns[existingList[i].GitHubRunID] = &existingList[i]
		}
	}

	var synced []string
	var skipped []string

	for _, ghRun := range ghRuns {
		fmt.Printf("[SyncRuns] Processing run #%d (github_id=%d, status=%s)\n", ghRun.RunNumber, ghRun.ID, ghRun.Status)

		runStatus := mapRunStatus(ghRun.Status)
		runConclusion := mapRunConclusion(ghRun.Conclusion)

		if existing, ok := existingRuns[ghRun.ID]; ok {
			// Update existing run
			changed := false
			if existing.Status != runStatus {
				existing.Status = runStatus
				changed = true
			}
			if existing.Conclusion != runConclusion {
				existing.Conclusion = runConclusion
				changed = true
			}
			if existing.HTMLURL != ghRun.HTMLURL {
				existing.HTMLURL = ghRun.HTMLURL
				changed = true
			}
			// Fetch/update jobs for completed runs
			if ghRun.Status == "completed" {
				fmt.Printf("[SyncRuns] Fetching jobs for existing run #%d\n", ghRun.RunNumber)
				if ghJobs, jobErr := svc.GetWorkflowRunJobs(decryptedToken, repo.FullName, ghRun.ID); jobErr == nil && len(ghJobs) > 0 {
					fmt.Printf("[SyncRuns] Got %d jobs for run #%d\n", len(ghJobs), ghRun.RunNumber)
					if bytes, marshalErr := json.Marshal(mapJobs(ghJobs)); marshalErr == nil {
						existing.Jobs = string(bytes)
						changed = true
					}
				} else if jobErr != nil {
					fmt.Printf("[SyncRuns] Failed to fetch jobs for run #%d: %v\n", ghRun.RunNumber, jobErr)
				}
			}
			if changed {
				if updateErr := h.runRepo.Update(existing); updateErr != nil {
					fmt.Printf("[SyncRuns] Failed to update run #%d: %v\n", ghRun.RunNumber, updateErr)
				} else {
					fmt.Printf("[SyncRuns] Updated existing run #%d\n", ghRun.RunNumber)
				}
			}
			if existing.Jobs != "" && existing.Jobs != "null" && existing.Jobs != "[]" {
				createAnalysisFromJobs(h.db, h.analysisRepo, h.aiService, existing, repo.FullName, decryptedToken)
			}
			synced = append(synced, fmt.Sprintf("#%d (github_run_id=%d) [updated]", ghRun.RunNumber, ghRun.ID))
		} else {
			// Create new run
			newRun := &models.PipelineRun{
				PipelineID:  pipeline.ID,
				RunNumber:   ghRun.RunNumber,
				GitHubRunID: ghRun.ID,
				Status:      runStatus,
				Conclusion:  runConclusion,
				HTMLURL:     ghRun.HTMLURL,
			}
			if ghRun.Status == "completed" {
				fmt.Printf("[SyncRuns] Fetching jobs for new run #%d\n", ghRun.RunNumber)
				if ghJobs, jobErr := svc.GetWorkflowRunJobs(decryptedToken, repo.FullName, ghRun.ID); jobErr == nil && len(ghJobs) > 0 {
					fmt.Printf("[SyncRuns] Got %d jobs for new run #%d\n", len(ghJobs), ghRun.RunNumber)
					if bytes, marshalErr := json.Marshal(mapJobs(ghJobs)); marshalErr == nil {
						newRun.Jobs = string(bytes)
					}
				} else if jobErr != nil {
					fmt.Printf("[SyncRuns] Failed to fetch jobs for new run #%d: %v\n", ghRun.RunNumber, jobErr)
				}
			}
			if createErr := h.runRepo.Create(newRun); createErr != nil {
				fmt.Printf("[SyncRuns] Failed to create run #%d: %v\n", ghRun.RunNumber, createErr)
				skipped = append(skipped, fmt.Sprintf("#%d (error: %v)", ghRun.RunNumber, createErr))
			} else {
				if newRun.Jobs != "" && newRun.Jobs != "null" && newRun.Jobs != "[]" {
					createAnalysisFromJobs(h.db, h.analysisRepo, h.aiService, newRun, repo.FullName, decryptedToken)
				}
				synced = append(synced, fmt.Sprintf("#%d (github_run_id=%d) [new]", ghRun.RunNumber, ghRun.ID))
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"message":       "sync complete",
		"workflow_file": usedWorkflowFile,
		"synced":        synced,
		"skipped":       skipped,
	})
}

// GET /api/v1/repositories/:repoId/pipelines/:version/runs/:runId/jobs/:jobId/log-findings
//
// Fetches the raw log of a single workflow job from GitHub and parses
// it into security findings using deterministic regex patterns keyed to
// the scanner family (Semgrep, Trivy, Gitleaks, npm audit, etc.). The
// response can be rendered directly in the run detail UI as a "Security
// Findings from Job Log" panel without a separate AI call.
func (h *PipelineHandler) GetJobLogFindings(c *gin.Context) {
	runIDStr := c.Param("runId")
	runID, err := uuid.Parse(runIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid run id"})
		return
	}
	jobIDStr := c.Param("jobId")
	jobID, err := strconv.ParseInt(jobIDStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid job id"})
		return
	}

	run, err := h.runRepo.FindByID(runID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByID(run.PipelineID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "pipeline lookup failed"})
		return
	}
	repo := pipeline.Repository
	if repo.AccessTokenEncrypted == "" || repo.FullName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repository has no GitHub token"})
		return
	}

	encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
	if len(encryptionKey) != 32 {
		fallback := make([]byte, 32)
		copy(fallback, "ai-devsecops-default-key-32bytes!")
		encryptionKey = fallback
	}
	decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey)
	if decryptErr != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to decrypt token: %v", decryptErr)})
		return
	}

	// Look up the job name from the cached jobs JSON so we can pass it
	// to the parser. Fall back to a generic label if it is missing.
	jobName := "unknown"
	if run.Jobs != "" && run.Jobs != "null" {
		var jobs []pipelineJob
		if json.Unmarshal([]byte(run.Jobs), &jobs) == nil {
			for _, j := range jobs {
				if j.ID == jobID {
					jobName = j.Name
					break
				}
			}
		}
	}

	svc := services.NewGitHubService()
	logText, logErr := svc.GetJobLogs(decryptedToken, repo.FullName, jobID)
	if logErr != nil {
		// If we cannot fetch the log (e.g. runner has not uploaded it
		// yet), still return a synthesized finding keyed to the job
		// name so the UI has something to show.
		logText = ""
		fmt.Printf("[GetJobLogFindings] WARNING: failed to fetch log for job %d: %v\n", jobID, logErr)
	}

	result := ParseJobLog(jobName, jobID, logText)
	c.JSON(http.StatusOK, result)
}

// GET /api/v1/repositories/:repoId/pipelines/:version/runs/:runId/raw-log
//
// Reviewer feedback: the user wants to see the raw workflow log
// content (the text GitHub Actions stored for the run) so they can
// verify the AI agent's findings. Returns the raw log text with
// per-job metadata. The text is truncated to a reasonable size
// to keep the response fast.
func (h *PipelineHandler) GetRunRawLog(c *gin.Context) {
	runIDStr := c.Param("runId")
	runID, err := uuid.Parse(runIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid run id"})
		return
	}

	run, err := h.runRepo.FindByID(runID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByID(run.PipelineID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "pipeline lookup failed"})
		return
	}
	repo := pipeline.Repository
	if repo.AccessTokenEncrypted == "" || repo.FullName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repository has no GitHub token"})
		return
	}

	encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
	if len(encryptionKey) != 32 {
		fallback := make([]byte, 32)
		copy(fallback, "ai-devsecops-default-key-32bytes!")
		encryptionKey = fallback
	}
	decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey)
	if decryptErr != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to decrypt token: %v", decryptErr)})
		return
	}

	// 1. Try fetching the full consolidated run log first (it
	//    contains every step from every job in one zip).
	svc := services.NewGitHubService()
	logText, logErr := svc.GetWorkflowRunLogs(decryptedToken, repo.FullName, run.GitHubRunID)
	source := "run_logs"
	if logErr != nil || logText == "" {
		// 2. Fallback: fetch each job's log individually. The
		//    GetJobLogs endpoint returns plain text (not zipped)
		//    so it is much easier to read in the UI.
		source = "per_job_logs"
		if jobsJSON := run.Jobs; jobsJSON != "" && jobsJSON != "null" {
			var jobs []pipelineJob
			if err := json.Unmarshal([]byte(jobsJSON), &jobs); err == nil {
				parts := []string{}
				for _, j := range jobs {
					jobLog, jErr := svc.GetJobLogs(decryptedToken, repo.FullName, j.ID)
					if jErr != nil || jobLog == "" {
						continue
					}
					parts = append(parts, fmt.Sprintf("=== Job: %s (id=%d, conclusion=%s) ===\n%s", j.Name, j.ID, j.Conclusion, jobLog))
				}
				logText = strings.Join(parts, "\n\n")
			}
		}
	}

	// Truncate to keep the response fast. ~5MB is plenty for
	// display; the AI agent operates on the un-truncated log.
	const maxBytes = 5 * 1024 * 1024
	truncated := false
	if len(logText) > maxBytes {
		logText = logText[:maxBytes]
		truncated = true
	}

	c.JSON(http.StatusOK, gin.H{
		"run_id":     runID,
		"log_text":   logText,
		"size":       len(logText),
		"truncated":  truncated,
		"source":     source,
		"fetched_at": time.Now().UTC().Format(time.RFC3339),
	})
}

// POST /api/v1/repositories/:repoId/pipelines/:version/runs/:runId/extract-all-job-findings
//
// Walks every job in the run, fetches the raw log from GitHub, and
// returns the union of parsed security findings. This is the
// "automation" entry point used by the run detail UI: the user clicks
// one button and the entire job log corpus is processed and rendered
// into the existing FindingsTable component (no per-job interaction
// required).
//
// The response is shaped to be drop-in compatible with the existing
// dashboard findings: each item is a Finding with a synthetic
// `category` of "security_finding" so FindingsTable renders it the
// same way as the AI analysis output.
//
// In addition to log parsing, the handler fetches the repository's
// GitHub Code Scanning alerts (SARIF uploads from Semgrep, Trivy,
// Gitleaks, etc.) — these are the canonical source of truth for
// detected vulnerabilities and are merged with log-parsed findings so
// the UI surfaces real vulnerabilities even when the scanner job
// itself failed before the log was emitted (e.g. workflow config
// errors). The two sources are deduplicated by (file, line, rule_id).
func (h *PipelineHandler) ExtractAllJobFindings(c *gin.Context) {
	runIDStr := c.Param("runId")
	runID, err := uuid.Parse(runIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid run id"})
		return
	}

	run, err := h.runRepo.FindByID(runID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByID(run.PipelineID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "pipeline lookup failed"})
		return
	}
	repo := pipeline.Repository
	if repo.AccessTokenEncrypted == "" || repo.FullName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "repository has no GitHub token"})
		return
	}

	encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
	if len(encryptionKey) != 32 {
		fallback := make([]byte, 32)
		copy(fallback, "ai-devsecops-default-key-32bytes!")
		encryptionKey = fallback
	}
	decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey)
	if decryptErr != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to decrypt token: %v", decryptErr)})
		return
	}

	// Parse the cached jobs JSON. If the run hasn't been synced yet,
	// return an empty result rather than failing the whole call.
	var cachedJobs []pipelineJob
	if run.Jobs != "" && run.Jobs != "null" {
		if err := json.Unmarshal([]byte(run.Jobs), &cachedJobs); err != nil {
			fmt.Printf("[ExtractAllJobFindings] WARNING: failed to parse cached jobs: %v\n", err)
		}
	}
	if len(cachedJobs) == 0 {
		c.JSON(http.StatusOK, gin.H{
			"message":        "no jobs to extract — run has not been synced yet",
			"findings":       []Finding{},
			"jobs_processed": 0,
			"jobs_failed":    0,
		})
		return
	}

	svc := services.NewGitHubService()

	type jobExtractionStatus struct {
		JobID         int64  `json:"job_id"`
		JobName       string `json:"job_name"`
		Conclusion    string `json:"conclusion"`
		Scanner       string `json:"scanner"`
		FindingsCount int    `json:"findings_count"`
		LogError      string `json:"log_error,omitempty"`
	}

	var allFindings []Finding
	var jobStatuses []jobExtractionStatus
	jobsFailed := 0

	for _, job := range cachedJobs {
		status := jobExtractionStatus{
			JobID:      job.ID,
			JobName:    job.Name,
			Conclusion: job.Conclusion,
		}

		logText, logErr := svc.GetJobLogs(decryptedToken, repo.FullName, job.ID)
		if logErr != nil {
			status.LogError = logErr.Error()
			jobsFailed++
			jobStatuses = append(jobStatuses, status)
			fmt.Printf("[ExtractAllJobFindings] WARNING: log fetch failed for job %d (%s): %v\n", job.ID, job.Name, logErr)
			continue
		}

		parsed := ParseJobLog(job.Name, job.ID, logText)
		status.Scanner = parsed.Scanner
		status.FindingsCount = len(parsed.Findings)
		jobStatuses = append(jobStatuses, status)

		for _, f := range parsed.Findings {
			// Tag the finding with a synthetic category and the source
			// job so FindingsTable can render it as a security finding
			// while still letting the user trace it back to the job
			// that produced it.
			tagged := f
			if tagged.Category == "" {
				tagged.Category = "security_finding"
			}
			if tagged.Job == "" {
				tagged.Job = job.Name
			}
			allFindings = append(allFindings, tagged)
		}
	}

	// Tier 2: fetch Code Scanning alerts (canonical source of truth
	// for SARIF-uploaded scanners). These exist even when the job
	// failed before the log was emitted, so we merge them with
	// log-parsed findings and deduplicate by (file, line, rule_id).
	codeScanningAlerts, csErr := svc.ListCodeScanningAlerts(decryptedToken, repo.FullName, 100)
	if csErr != nil {
		fmt.Printf("[ExtractAllJobFindings] WARNING: code scanning alerts fetch failed: %v\n", csErr)
	} else {
		fmt.Printf("[ExtractAllJobFindings] Fetched %d code scanning alerts\n", len(codeScanningAlerts))
		seen := make(map[string]bool)
		for _, a := range allFindings {
			key := fmt.Sprintf("%s:%d:%s", a.FileLocation, a.Line, a.RuleID)
			seen[key] = true
		}
		codeScanningCount := 0
		for _, a := range codeScanningAlerts {
			key := fmt.Sprintf("%s:%d:%s", a.FilePath, a.StartLine, a.RuleID)
			if seen[key] {
				continue
			}
			seen[key] = true

			severity := mapGitHubSeverity(a)
			f := Finding{
				Title:                     a.RuleDescription,
				Severity:                  severity,
				SourceTool:                a.Tool,
				Scanner:                   a.Tool,
				Evidence:                  a.Message,
				FileLocation:              a.FilePath,
				Line:                      a.StartLine,
				Type:                      "code_scanning_alert",
				Category:                  "security_finding",
				CWE:                       a.CWE,
				RuleID:                    a.RuleID,
				RemediationRecommendation: "Open the alert on GitHub to view the suggested fix: " + a.HTMLURL,
				Recommendation:            "See the rule docs and remediate the issue at " + a.HTMLURL,
			}
			allFindings = append(allFindings, f)
			codeScanningCount++
		}
		fmt.Printf("[ExtractAllJobFindings] Added %d code scanning alerts (dedup against log)\n", codeScanningCount)
	}

	c.JSON(http.StatusOK, gin.H{
		"message":        "extraction complete",
		"jobs_processed": len(cachedJobs) - jobsFailed,
		"jobs_failed":    jobsFailed,
		"findings":       allFindings,
		"jobs":           jobStatuses,
	})
}

// mapGitHubSeverity maps a GitHub Code Scanning alert's severity
// fields to the Finding severity scale used by the rest of the app
// (critical|high|medium|low). The alert API returns two fields:
//   - rule_severity: from the rule itself (none, note, warning, error, or
//     custom label)
//   - security_severity: from the security-severity tag in SARIF, if
//     present (low, medium, high, critical)
//
// We prefer security_severity when available because it is more
// standardized for security tools.
func mapGitHubSeverity(a services.CodeScanningAlert) string {
	if a.SecuritySeverity != "" {
		switch strings.ToLower(a.SecuritySeverity) {
		case "critical":
			return "critical"
		case "high":
			return "high"
		case "medium":
			return "medium"
		case "low":
			return "low"
		}
	}
	switch strings.ToLower(a.RuleSeverity) {
	case "critical", "error":
		return "critical"
	case "high", "warning":
		return "high"
	case "medium", "note":
		return "medium"
	default:
		return "low"
	}
}

func mapRunStatus(status string) models.RunStatus {
	switch status {
	case "queued", "waiting":
		return models.RunStatusQueued
	case "in_progress":
		return models.RunStatusRunning
	case "completed":
		return models.RunStatusCompleted
	default:
		return models.RunStatusPending
	}
}

func mapRunConclusion(conclusion string) models.RunConclusion {
	switch conclusion {
	case "success":
		return models.RunConclusionSuccess
	case "failure":
		return models.RunConclusionFailure
	case "cancelled":
		return models.RunConclusionCancelled
	case "skipped":
		return models.RunConclusionSkipped
	case "timed_out":
		return models.RunConclusionFailure
	default:
		return ""
	}
}

type pipelineJob struct {
	ID         int64          `json:"id"`
	Name       string         `json:"name"`
	Status     string         `json:"status"`
	Conclusion string         `json:"conclusion"`
	Steps      []pipelineStep `json:"steps"`
}
type pipelineStep struct {
	Name       string `json:"name"`
	Status     string `json:"status"`
	Conclusion string `json:"conclusion"`
	Number     int    `json:"number"`
}

func mapJobs(ghJobs []services.WorkflowJob) []pipelineJob {
	var mapped []pipelineJob
	for _, j := range ghJobs {
		var steps []pipelineStep
		for _, s := range j.Steps {
			steps = append(steps, pipelineStep{
				Name:       s.Name,
				Status:     s.Status,
				Conclusion: s.Conclusion,
				Number:     s.Number,
			})
		}
		mapped = append(mapped, pipelineJob{
			ID:         j.ID,
			Name:       j.Name,
			Status:     j.Status,
			Conclusion: j.Conclusion,
			Steps:      steps,
		})
	}
	return mapped
}

func createAnalysisFromJobs(db *gorm.DB, analysisRepo repositories.PipelineAnalysisRepository, aiService *services.AIService, run *models.PipelineRun, repoFullName string, githubToken string) {
	if run.Jobs == "" || run.Jobs == "null" {
		fmt.Printf("[Analysis] SKIP: run %s has no jobs\n", run.ID)
		return
	}

	var jobs []struct {
		Name       string `json:"name"`
		Status     string `json:"status"`
		Conclusion string `json:"conclusion"`
	}
	if err := json.Unmarshal([]byte(run.Jobs), &jobs); err != nil || len(jobs) == 0 {
		fmt.Printf("[Analysis] SKIP: run %s failed to parse jobs: %v, job count: %d\n", run.ID, err, len(jobs))
		return
	}

	var findings []Finding
	var recommendations []Recommendation
	severityBreakdown := map[string]int{"critical": 0, "high": 0, "medium": 0, "low": 0}
	var riskScore, complianceScore, securityCoverageScore float64
	var aiFailed bool
	var dashboard DashboardFindings

	// Step 1: Fetch GitHub annotations as the primary evidence source.
	// Annotations are only used when GitHub credentials are available.
	var annotationDashboard DashboardFindings
	if githubToken != "" && repoFullName != "" && run.GitHubRunID > 0 {
		ghSvc := services.NewGitHubService()
		annotations, err := ghSvc.GetRunAnnotations(githubToken, repoFullName, run.GitHubRunID)
		if err != nil {
			fmt.Printf("[Analysis] WARNING: failed to fetch annotations for run %s: %v\n", run.ID, err)
		} else {
			fmt.Printf("[Analysis] Fetched %d annotations for run %s\n", len(annotations), run.ID)
			annotationDashboard = buildDashboardFromAnnotations(annotations)
		}
	}

	// Step 2: AI service call for risk scores and additional findings.
	if aiService != nil && run.GitHubRunID > 0 && repoFullName != "" && githubToken != "" {
		fmt.Printf("[Analysis] Calling AI service for run %s (github_run_id=%d)\n", run.ID, run.GitHubRunID)
		aiResult, err := aiService.AnalyzeExecution(repoFullName, int(run.GitHubRunID), githubToken)
		if err != nil {
			fmt.Printf("[Analysis] AI service failed for run %s: %v\n", run.ID, err)
			aiFailed = true
		} else {
			// Even if Errors are populated, we still want to ingest
			// the partial result (risk_score, findings, severity
			// breakdown). Errors only indicate that some downstream
			// sub-step (e.g. recommendation generation) failed —
			// the OWASP risk score is still valid.
			if len(aiResult.Errors) > 0 {
				fmt.Printf("[Analysis] AI service returned %d non-fatal errors for run %s: %v\n", len(aiResult.Errors), run.ID, aiResult.Errors)
			}
			fmt.Printf("[Analysis] AI service returned %d findings for run %s (risk_score=%.1f, level=%s)\n", len(aiResult.Findings), run.ID, aiResult.RiskScore, aiResult.RiskLevel)
			riskScore = aiResult.RiskScore
			complianceScore = aiResult.ComplianceScore
			securityCoverageScore = aiResult.SecurityCoverageScore
			if aiResult.SeverityBreakdown != nil {
				severityBreakdown = aiResult.SeverityBreakdown
			}
			findings = aiFindingsToBackendFindings(aiResult.Findings)
			recommendations = aiRecsToBackendRecommendations(aiResult.Recommendations)
			aiDashboard := aiDashboardToBackendDashboard(aiResult.DashboardFindings)
			dashboard = mergeAnnotationsWithAIDashboard(aiDashboard, annotationDashboard)
		}
	} else {
		aiFailed = true
		fmt.Printf("[Analysis] AI service skipped for run %s (missing deps)\n", run.ID)
	}

	// Step 3: Use annotation dashboard as fallback when AI service didn't produce one.
	if aiFailed || (len(dashboard.SecurityFindings) == 0 && len(dashboard.WorkflowConfigIssues) == 0 &&
		len(dashboard.MaintenanceWarnings) == 0 && len(dashboard.ExternalServiceIssues) == 0) {
		dashboard = annotationDashboard
	}

	// Risk score: only reflects validated security findings.
	// When annotations provided security findings but AI service was unavailable,
	// keep the risk score at neutral (100) since annotation severity scoring
	// is not as nuanced.
	if len(findings) == 0 {
		if len(dashboard.SecurityFindings) == 0 {
			riskScore = 100
		} else if aiFailed {
			riskScore = 50
		}
	}

	// Ensure the findings list is NOT derived from annotation dashboard
	// (findings list is AI-only). Dashboard sections are annotation-only.
	if aiFailed {
		dashboard.Message = "No validated security findings detected. Workflow issues may still exist."
	}

	if dashboard.Message == "" && len(dashboard.SecurityFindings) == 0 {
		dashboard.Message = "No validated security findings detected. Workflow issues may still exist."
	}

	rawScanData := map[string]any{
		"dashboard_findings": dashboard,
		"findings":           findings,
		"recommendations":    recommendations,
		"ai_failed":          aiFailed,
	}
	rawScanBytes, _ := json.Marshal(rawScanData)

	findingsBytes, _ := json.Marshal(findings)
	severityBytes, _ := json.Marshal(severityBreakdown)
	recBytes, _ := json.Marshal(recommendations)

	const workflowQualityScore = 0

	existingAnalysis, findErr := analysisRepo.FindByRunID(run.ID)
	if findErr != nil || existingAnalysis == nil {
		db.Exec(`DELETE FROM pipeline_analyses WHERE pipeline_run_id = ?`, run.ID)
		db.Exec(`
			INSERT INTO pipeline_analyses (id, pipeline_run_id, risk_score, compliance_score, workflow_quality_score, security_coverage_score, findings_summary, severity_breakdown, recommendations, raw_scan_data, created_at)
			VALUES (gen_random_uuid(), ?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?::jsonb, ?::jsonb, NOW())
		`, run.ID, riskScore, complianceScore, workflowQualityScore, securityCoverageScore, string(findingsBytes), string(severityBytes), string(recBytes), string(rawScanBytes))
		fmt.Printf("[Analysis] CREATED analysis for run %s: risk=%.1f, compliance=%.1f, coverage=%.1f\n", run.ID, riskScore, complianceScore, securityCoverageScore)
	} else {
		db.Exec(`
			UPDATE pipeline_analyses SET
				risk_score = ?,
				compliance_score = ?,
				workflow_quality_score = ?,
				security_coverage_score = ?,
				findings_summary = ?::jsonb,
				severity_breakdown = ?::jsonb,
				recommendations = ?::jsonb,
				raw_scan_data = ?::jsonb,
				created_at = NOW()
			WHERE pipeline_run_id = ?
		`, riskScore, complianceScore, workflowQualityScore, securityCoverageScore, string(findingsBytes), string(severityBytes), string(recBytes), string(rawScanBytes), run.ID)
		fmt.Printf("[Analysis] UPDATED analysis for run %s: risk=%.1f, compliance=%.1f, coverage=%.1f\n", run.ID, riskScore, complianceScore, securityCoverageScore)
	}
}

func aiFindingsToBackendFindings(aiFindings []any) []Finding {
	var findings []Finding
	for _, raw := range aiFindings {
		data, ok := raw.(map[string]any)
		if !ok {
			continue
		}

		f := Finding{
			Title:                     toString(firstNonEmpty(data["title"], data["type"])),
			SourceTool:                toString(firstNonEmpty(data["source_tool"], data["scanner"])),
			Severity:                  toString(data["severity"]),
			Evidence:                  toString(firstNonEmpty(data["evidence"], data["explanation"], data["message"])),
			FileLocation:              toString(firstNonEmpty(data["file_location"], data["file"], data["path"])),
			RemediationRecommendation: toString(firstNonEmpty(data["remediation_recommendation"], data["recommendation"], data["suggestion"])),
			Type:                      toString(data["type"]),
			CodeSnippet:               toString(data["code_snippet"]),
			CWE:                       toString(data["cwe"]),
			OWASP:                     toString(data["owasp"]),
			CVE:                       toString(data["cve"]),
			PackageName:               toString(data["package_name"]),
			InstalledVersion:          toString(data["installed_version"]),
			FixedVersion:              toString(data["fixed_version"]),
			Scanner:                   toString(firstNonEmpty(data["scanner"], data["source_tool"])),
			Explanation:               toString(firstNonEmpty(data["explanation"], data["evidence"], data["message"])),
			Recommendation:            toString(firstNonEmpty(data["recommendation"], data["remediation_recommendation"], data["suggestion"])),
		}
		if line, ok := data["line"].(float64); ok {
			f.Line = int(line)
		}
		if f.Type == "" {
			f.Type = "security_finding"
		}
		if f.Severity == "" {
			f.Severity = "medium"
		}
		if f.Title == "" {
			f.Title = fmt.Sprintf("%s finding", f.Type)
		}
		if f.SourceTool == "" {
			f.SourceTool = f.Scanner
		}
		if f.Scanner == "" {
			f.Scanner = f.SourceTool
		}
		findings = append(findings, f)
	}
	return findings
}

func firstNonEmpty(values ...any) any {
	for _, v := range values {
		if s := toString(v); s != "" {
			return s
		}
	}
	return ""
}

func aiRecsToBackendRecommendations(aiRecs []any) []Recommendation {
	var recs []Recommendation
	for i, raw := range aiRecs {
		var title, desc string
		switch v := raw.(type) {
		case string:
			title = fmt.Sprintf("Recommendation %d", i+1)
			desc = v
		case map[string]any:
			title = toString(v["title"])
			desc = toString(v["description"])
			if title == "" {
				title = toString(v["finding_type"])
			}
		}
		if title == "" {
			title = fmt.Sprintf("Recommendation %d", i+1)
		}
		recs = append(recs, Recommendation{Title: title, Description: desc, Priority: "high"})
	}
	return recs
}

func aiDashboardToBackendDashboard(raw any) DashboardFindings {
	data, ok := raw.(map[string]any)
	if !ok {
		return DashboardFindings{Message: "No validated security findings detected. Workflow issues may still exist."}
	}

	security := aiFindingsToBackendFindings(_anySlice(data["security_finding"]))
	config := aiFindingsToBackendFindings(_anySlice(data["workflow_config_issue"]))
	maintenance := aiFindingsToBackendFindings(_anySlice(data["maintenance_warning"]))
	external := aiFindingsToBackendFindings(_anySlice(data["external_service_issue"]))

	return DashboardFindings{
		SecurityFindings:      security,
		WorkflowConfigIssues:  config,
		MaintenanceWarnings:   maintenance,
		ExternalServiceIssues: external,
		SecurityCount:         _intFromAny(data["security_count"]),
		WorkflowConfigCount:   _intFromAny(data["workflow_config_count"]),
		MaintenanceCount:      _intFromAny(data["maintenance_count"]),
		ExternalCount:         _intFromAny(data["external_count"]),
		TotalCount:            _intFromAny(data["total_count"]),
		Message:               toString(data["message"]),
	}
}

func _anySlice(v any) []any {
	if v == nil {
		return nil
	}
	if s, ok := v.([]any); ok {
		return s
	}
	return nil
}

func _intFromAny(v any) int {
	if v == nil {
		return 0
	}
	switch n := v.(type) {
	case float64:
		return int(n)
	case float32:
		return int(n)
	case int:
		return n
	case int64:
		return int(n)
	case string:
		if i, err := strconv.Atoi(n); err == nil {
			return i
		}
	}
	return 0
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprintf("%v", v)
}

type Finding struct {
	Title                     string `json:"title"`
	SourceTool                string `json:"source_tool"`
	Severity                  string `json:"severity"`
	Evidence                  string `json:"evidence"`
	FileLocation              string `json:"file_location,omitempty"`
	Line                      int    `json:"line,omitempty"`
	RemediationRecommendation string `json:"remediation_recommendation"`
	Type                      string `json:"type"`
	CodeSnippet               string `json:"code_snippet,omitempty"`
	CWE                       string `json:"cwe,omitempty"`
	OWASP                     string `json:"owasp,omitempty"`
	CVE                       string `json:"cve,omitempty"`
	PackageName               string `json:"package_name,omitempty"`
	InstalledVersion          string `json:"installed_version,omitempty"`
	FixedVersion              string `json:"fixed_version,omitempty"`
	Scanner                   string `json:"scanner,omitempty"`
	Explanation               string `json:"explanation,omitempty"`
	Recommendation            string `json:"recommendation,omitempty"`
	RuleID                    string `json:"rule_id,omitempty"`
	Category                  string `json:"category,omitempty"`
	Job                       string `json:"job,omitempty"`
}

type Recommendation struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Priority    string `json:"priority,omitempty"`
}

type DashboardFindings struct {
	SecurityFindings      []Finding `json:"security_finding"`
	WorkflowConfigIssues  []Finding `json:"workflow_config_issue"`
	MaintenanceWarnings   []Finding `json:"maintenance_warning"`
	ExternalServiceIssues []Finding `json:"external_service_issue"`
	SecurityCount         int       `json:"security_count"`
	WorkflowConfigCount   int       `json:"workflow_config_count"`
	MaintenanceCount      int       `json:"maintenance_count"`
	ExternalCount         int       `json:"external_count"`
	TotalCount            int       `json:"total_count"`
	Message               string    `json:"message,omitempty"`
}

func roundFloat(v float64) float64 {
	return float64(int(v*10)) / 10
}

// GET /api/v1/runs/:runId
func (h *PipelineHandler) GetRun(c *gin.Context) {
	runID, err := uuid.Parse(c.Param("runId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid run id"})
		return
	}

	run, err := h.runRepo.FindByID(runID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	// If jobs already in DB, return immediately (don't hit GitHub on every request)
	if run.Jobs != "" && run.Jobs != "null" && run.Jobs != "[]" {
		c.JSON(http.StatusOK, run)
		return
	}

	// Try to fetch jobs from GitHub only if not already cached
	if run.GitHubRunID > 0 {
		if run.Pipeline.Repository.FullName == "" {
			fmt.Printf("[GetRun] WARNING: run %s has no repository (pipeline not loaded?)\n", runID)
		} else if run.Pipeline.Repository.AccessTokenEncrypted == "" {
			fmt.Printf("[GetRun] WARNING: run %s has no GitHub token in DB\n", runID)
		} else {
			repo := run.Pipeline.Repository
			svc := services.NewGitHubService()

			encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
			if len(encryptionKey) != 32 {
				fmt.Printf("[GetRun] WARNING: encryption key not 32 bytes, using fallback\n")
				fallback := make([]byte, 32)
				copy(fallback, "ai-devsecops-default-key-32bytes!")
				encryptionKey = fallback
			}

			decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey)
			if decryptErr != nil {
				fmt.Printf("[GetRun] ERROR: token decryption failed for run %s: %v\n", runID, decryptErr)
				fmt.Printf("[GetRun]   encrypted token length: %d\n", len(repo.AccessTokenEncrypted))
				fmt.Printf("[GetRun]   encryption key hex: %s\n", hex.EncodeToString(encryptionKey))
				c.JSON(http.StatusOK, run)
				return
			}

			// Fetch run status/conclusion from GitHub
			ghRun, err := svc.GetWorkflowRun(decryptedToken, repo.FullName, run.GitHubRunID)
			if err != nil {
				fmt.Printf("[GetRun] ERROR: failed to fetch run from GitHub (run_id=%d, repo=%s): %v\n", run.GitHubRunID, repo.FullName, err)
			} else if ghRun != nil {
				run.Status = models.RunStatus("completed")
				if ghRun.Conclusion == "success" || ghRun.Conclusion == "failure" || ghRun.Conclusion == "cancelled" {
					run.Conclusion = models.RunConclusion(ghRun.Conclusion)
				}
				run.HTMLURL = ghRun.HTMLURL
			}

			// Fetch jobs from GitHub
			ghJobs, err := svc.GetWorkflowRunJobs(decryptedToken, repo.FullName, run.GitHubRunID)
			if err != nil {
				fmt.Printf("[GetRun] ERROR: failed to fetch jobs from GitHub (run_id=%d): %v\n", run.GitHubRunID, err)
			} else if len(ghJobs) > 0 {
				fmt.Printf("[GetRun] SUCCESS: fetched %d jobs for run %s\n", len(ghJobs), runID)
				type jobStep struct {
					Name       string `json:"name"`
					Status     string `json:"status"`
					Conclusion string `json:"conclusion"`
					Number     int    `json:"number"`
				}
				type pipelineJob struct {
					ID         int64     `json:"id"`
					Name       string    `json:"name"`
					Status     string    `json:"status"`
					Conclusion string    `json:"conclusion"`
					Steps      []jobStep `json:"steps"`
				}
				var mapped []pipelineJob
				for _, j := range ghJobs {
					var steps []jobStep
					for _, s := range j.Steps {
						steps = append(steps, jobStep{
							Name:       s.Name,
							Status:     s.Status,
							Conclusion: s.Conclusion,
							Number:     s.Number,
						})
					}
					mapped = append(mapped, pipelineJob{
						ID:         j.ID,
						Name:       j.Name,
						Status:     j.Status,
						Conclusion: j.Conclusion,
						Steps:      steps,
					})
				}
				bytes, _ := json.Marshal(mapped)
				run.Jobs = string(bytes)
			} else {
				fmt.Printf("[GetRun] WARNING: no jobs returned from GitHub for run %d\n", run.GitHubRunID)
			}

			if updateErr := h.runRepo.Update(run); updateErr != nil {
				fmt.Printf("[GetRun] ERROR: failed to update run in DB: %v\n", updateErr)
			}
		}
	}

	c.JSON(http.StatusOK, run)
}

// GET /api/v1/runs/:runId/analysis
func (h *PipelineHandler) GetAnalysis(c *gin.Context) {
	runID, err := uuid.Parse(c.Param("runId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid run id"})
		return
	}

	analysis, err := h.analysisRepo.FindByRunID(runID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "analysis not found"})
		return
	}

	var dashboard DashboardFindings
	var rawFindings []Finding
	if analysis.RawScanData != "" && analysis.RawScanData != "null" && analysis.RawScanData != "{}" {
		var raw map[string]any
		if json.Unmarshal([]byte(analysis.RawScanData), &raw) == nil {
			dashboard = aiDashboardToBackendDashboard(raw["dashboard_findings"])
			if rawFindingsRaw, ok := raw["findings"].([]any); ok {
				rawFindings = aiFindingsToBackendFindings(rawFindingsRaw)
			}
		}
	}

	if dashboard.Message == "" && len(dashboard.SecurityFindings) == 0 {
		dashboard.Message = "No validated security findings detected. Workflow issues may still exist."
	}

	var findings []Finding
	if analysis.FindingsSummary != "" && analysis.FindingsSummary != "null" && analysis.FindingsSummary != "[]" {
		json.Unmarshal([]byte(analysis.FindingsSummary), &findings)
	}
	if len(findings) == 0 && len(rawFindings) > 0 {
		findings = rawFindings
	}

	var severityBreakdown map[string]int
	if analysis.SeverityBreakdown != "" && analysis.SeverityBreakdown != "null" && analysis.SeverityBreakdown != "{}" {
		json.Unmarshal([]byte(analysis.SeverityBreakdown), &severityBreakdown)
	}

	var recommendations []Recommendation
	if analysis.Recommendations != "" && analysis.Recommendations != "null" && analysis.Recommendations != "[]" {
		recsRaw := []any{}
		if json.Unmarshal([]byte(analysis.Recommendations), &recsRaw) == nil {
			recommendations = aiRecsToBackendRecommendations(recsRaw)
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"id":                           analysis.ID,
		"pipeline_run_id":              analysis.PipelineRunID,
		"risk_score":                   analysis.RiskScore,
		"compliance_score":             analysis.ComplianceScore,
		"security_coverage_score":      analysis.SecurityCoverageScore,
		"findings":                     findings,
		"severity_breakdown":           severityBreakdown,
		"recommendations":              recommendations,
		"ai_explanation":               analysis.AIExplanation,
		"created_at":                   analysis.CreatedAt,
		"dashboard_findings":           dashboard,
		"no_security_findings_message": dashboard.Message,
	})
}

// GET /api/v1/repositories/:repoId/insights
func (h *PipelineHandler) GetInsights(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	insight, err := h.insightRepo.FindByRepository(repoID)
	if err != nil {
		c.JSON(http.StatusOK, nil)
		return
	}

	c.JSON(http.StatusOK, insight)
}

// GET /api/v1/repositories/:repoId/pipeline-summary
//
// Bab 5.13.5: returns the cached Tahap-1 / Tahap-2 detection
// (technologies, architecture, deployment) in the same shape
// the AI service's `RepoPipelineResult` exposes to the FE. The
// RunDetail page uses this as a fallback when the AI service's
// `POST /ai/pipeline/repo/pipeline` call is slow or fails —
// the Go side already persists these fields on
// `repository_insights` so the PDF cover page never reads
// "Architecture: — | Domain: —".
func (h *PipelineHandler) GetPipelineSummary(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	var repo models.Repository
	if err := h.db.WithContext(c.Request.Context()).First(&repo, "id = ?", repoID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "repository not found"})
		return
	}

	insight, err := h.insightRepo.FindByRepository(repoID)
	if err != nil || insight == nil {
		// No cached insight yet — return a minimal shape so the
		// FE can still detect the empty state.
		c.JSON(http.StatusOK, gin.H{
			"repository_full_name":  repo.FullName,
			"has_insight":           false,
			"detected_technologies": gin.H{},
			"detected_architecture": gin.H{},
			"detected_deployment":   gin.H{},
		})
		return
	}

	// Frameworks / build tools / package managers / test
	// frameworks are stored as JSONB strings. Unmarshall each
	// one; fall back to an empty list when the column is
	// missing or malformed so the FE can still render an empty
	// string instead of "—".
	var frameworks, buildTools, packageManagers, testFrameworks []string
	if insight.Frameworks != "" && insight.Frameworks != "null" && insight.Frameworks != "[]" {
		_ = json.Unmarshal([]byte(insight.Frameworks), &frameworks)
	}
	if insight.BuildTools != "" && insight.BuildTools != "null" && insight.BuildTools != "[]" {
		_ = json.Unmarshal([]byte(insight.BuildTools), &buildTools)
	}
	if insight.PackageManagers != "" && insight.PackageManagers != "null" && insight.PackageManagers != "[]" {
		_ = json.Unmarshal([]byte(insight.PackageManagers), &packageManagers)
	}
	if insight.TestFrameworks != "" && insight.TestFrameworks != "null" && insight.TestFrameworks != "[]" {
		_ = json.Unmarshal([]byte(insight.TestFrameworks), &testFrameworks)
	}

	pkg := ""
	if len(packageManagers) > 0 {
		pkg = packageManagers[0]
	}

	c.JSON(http.StatusOK, gin.H{
		"repository_full_name": repo.FullName,
		"has_insight":          true,
		"detected_technologies": gin.H{
			"primary_language": insight.PrimaryLanguage,
			"frameworks":       frameworks,
			"build_tools":      buildTools,
			"package_manager":  pkg,
			"test_framework":   ifFirst(testFrameworks),
		},
		"detected_architecture": gin.H{
			"architecture_type": insight.ArchitectureType,
		},
		"detected_architecture_type": insight.ArchitectureType,
		"detected_deployment": gin.H{
			"docker":         insight.HasDockerfile,
			"kubernetes":     insight.HasKubernetes,
			"terraform":      insight.HasTerraform,
			"helm":           false,
			"cloud_provider": nil,
		},
		"recommended_deployment_target": nil,
		"detected_domain":               "general",
		"domain_sub_type":               "none",
		"domain_confidence":             0.0,
		"domain_threats":                []string{},
		"features":                      []string{},
		"security_coverages":            []gin.H{},
		"pipeline_augmentations":        []gin.H{},
		"generated_workflow":            "",
		"generated_stages":              []string{},
		"validation_passed":             true,
		"errors":                        []string{},
		"_source":                       "go_repository_insight",
	})
}

// ifFirst returns the first element of a string slice, or "" if
// the slice is empty. Tiny helper to keep the JSON shape tidy.
func ifFirst(s []string) string {
	if len(s) == 0 {
		return ""
	}
	return s[0]
}

func calcSuccessRate(runs []models.PipelineRun) float64 {
	if len(runs) == 0 {
		return 0
	}
	successCount := 0
	for _, r := range runs {
		if r.Conclusion == models.RunConclusionSuccess {
			successCount++
		}
	}
	return float64(successCount) / float64(len(runs)) * 100
}

func latestCompletedRun(runs []models.PipelineRun) models.PipelineRun {
	for _, r := range runs {
		if r.Conclusion != "" {
			return r
		}
	}
	if len(runs) > 0 {
		return runs[0]
	}
	return models.PipelineRun{}
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

func delta(b, a float64, higherIsBetter bool) float64 {
	if higherIsBetter {
		return b - a
	}
	return a - b
}

// POST /api/v1/repositories/:repoId/pipelines/generate
type generatePipelineRequest struct {
	Query                string   `json:"query"`
	Language             string   `json:"language"`
	Framework            string   `json:"framework"`
	DeployTarget         string   `json:"deploy_target"`
	ProjectType          string   `json:"project_type"`
	SecurityRequirements []string `json:"security_requirements"`
}

func (h *PipelineHandler) Generate(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	var repoFull struct {
		FullName             string
		AccessTokenEncrypted string
		ProjectID            uuid.UUID
	}
	h.db.Table("repositories").Select("full_name, access_token_encrypted, project_id").Where("id = ?", repoID).Scan(&repoFull)
	if repoFull.FullName == "" {
		c.JSON(http.StatusNotFound, gin.H{"error": "repository not found"})
		return
	}

	var req generatePipelineRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userIDStr, _ := c.Get("userID")
	projectIDStr := repoFull.ProjectID.String()

	githubToken := ""
	if repoFull.AccessTokenEncrypted != "" {
		encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
		if len(encryptionKey) != 32 {
			fallback := make([]byte, 32)
			copy(fallback, "ai-devsecops-default-key-32bytes!")
			encryptionKey = fallback
		}
		decryptedToken, decryptErr := utils.DecryptAES(repoFull.AccessTokenEncrypted, encryptionKey)
		if decryptErr == nil {
			githubToken = decryptedToken
		}
	}

	aiReq := services.GenerateRequest{
		// AI service uses 'repository_id' as the GitHub repo identifier
		// (e.g. 'owner/repo'). Passing the UUID here would cause
		// GitHub API calls to 404 ('repos/<uuid>'). Use FullName.
		RepositoryID:         repoFull.FullName,
		RepositoryFullName:   repoFull.FullName,
		GitHubToken:          githubToken,
		ProjectID:            projectIDStr,
		Query:                req.Query,
		Language:             req.Language,
		Framework:            req.Framework,
		DeployTarget:         req.DeployTarget,
		ProjectType:          req.ProjectType,
		SecurityRequirements: req.SecurityRequirements,
	}

	// Re-use cached repository insights to avoid redundant detection LLM calls.
	insight, err := h.insightRepo.FindByRepository(repoID)
	if err == nil && insight != nil {
		fmt.Printf("[Generate] Reusing cached repository insights for %s\n", repoFull.FullName)
		cached := map[string]interface{}{
			"technologies": map[string]interface{}{
				"primary_language": insight.PrimaryLanguage,
			},
			"architecture_type": insight.ArchitectureType,
			"deployment": map[string]interface{}{
				"docker":     insight.HasDockerfile,
				"kubernetes": insight.HasKubernetes,
				"terraform":  insight.HasTerraform,
			},
		}
		if insight.Frameworks != "" && insight.Frameworks != "null" && insight.Frameworks != "[]" {
			var frameworks []string
			if json.Unmarshal([]byte(insight.Frameworks), &frameworks) == nil {
				cached["technologies"].(map[string]interface{})["frameworks"] = frameworks
			}
		}
		if insight.BuildTools != "" && insight.BuildTools != "null" && insight.BuildTools != "[]" {
			var buildTools []string
			if json.Unmarshal([]byte(insight.BuildTools), &buildTools) == nil {
				cached["technologies"].(map[string]interface{})["build_tools"] = buildTools
			}
		}
		if insight.DependencyEcosystem != "" && insight.DependencyEcosystem != "null" && insight.DependencyEcosystem != "[]" {
			var ecosystems []string
			if json.Unmarshal([]byte(insight.DependencyEcosystem), &ecosystems) == nil {
				cached["technologies"].(map[string]interface{})["package_manager"] = ecosystems
			}
		}
		if insight.RawAnalysisOutput != "" && insight.RawAnalysisOutput != "null" {
			var raw map[string]interface{}
			if json.Unmarshal([]byte(insight.RawAnalysisOutput), &raw) == nil {
				if tech, ok := raw["technologies"].(map[string]interface{}); ok {
					cached["technologies"] = tech
				}
				if arch, ok := raw["architecture"].(map[string]interface{}); ok {
					cached["architecture"] = arch
				}
				if dep, ok := raw["deployment"].(map[string]interface{}); ok {
					cached["deployment"] = dep
				}
				if sec, ok := raw["security_requirements"].(map[string]interface{}); ok {
					cached["security_needs"] = sec
				}
			}
		}
		aiReq.CachedInsights = cached
	} else {
		fmt.Printf("[Generate] No cached insights found for %s, running full analysis\n", repoFull.FullName)
	}

	aiResp, err := h.aiService.Generate(aiReq)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("AI service error: %v", err)})
		return
	}

	if len(aiResp.Errors) > 0 && aiResp.GeneratedWorkflow == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": aiResp.Errors[0], "errors": aiResp.Errors})
		return
	}

	nextVersion, _ := h.pipelineRepo.GetNextVersion(repoID)

	stagesJSON, _ := json.Marshal(aiResp.GeneratedStages)
	validationJSON, _ := json.Marshal(map[string]any{
		"valid":    aiResp.ValidationPassed,
		"errors":   aiResp.ValidationErrors,
		"warnings": aiResp.ValidationWarnings,
	})
	genParamsJSON, _ := json.Marshal(map[string]any{
		"project_id":            projectIDStr,
		"user_id":               userIDStr.(string),
		"language":              req.Language,
		"framework":             req.Framework,
		"deploy_target":         req.DeployTarget,
		"project_type":          req.ProjectType,
		"security_requirements": req.SecurityRequirements,
	})
	securityControlsJSON, _ := json.Marshal(aiResp.GeneratedStages)

	deploymentResultsJSON := ""
	if aiResp.GitHubPRURL != "" || aiResp.WorkflowFile != "" {
		depMap := map[string]any{
			"branch":        aiResp.GitHubBranch,
			"pr_number":     aiResp.GitHubPRNumber,
			"pr_url":        aiResp.GitHubPRURL,
			"workflow_file": aiResp.WorkflowFile,
		}
		if bytes, err := json.Marshal(depMap); err == nil {
			deploymentResultsJSON = string(bytes)
		}
	}

	status := models.PipelineStatusGenerated
	if aiResp.ValidationPassed {
		status = models.PipelineStatusValidated
	}

	pipeline := &models.Pipeline{
		ID:                      uuid.New(),
		RepositoryID:            repoID,
		VersionNumber:           nextVersion,
		Prompt:                  req.Query,
		GeneratedYAML:           aiResp.GeneratedWorkflow,
		Stages:                  string(stagesJSON),
		AIExplanation:           aiResp.Explanation,
		GenerationParams:        string(genParamsJSON),
		ValidationResults:       string(validationJSON),
		DeploymentResults:       deploymentResultsJSON,
		SecurityControlsApplied: string(securityControlsJSON),
		ComplianceMetadata:      "{}",
		NodeIO:                  marshalNodeIO(aiResp.NodeIO),
		Status:                  status,
	}

	if err := h.pipelineRepo.Create(pipeline); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to save pipeline: %v", err)})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"pipeline":            pipeline,
		"validation_passed":   aiResp.ValidationPassed,
		"validation_errors":   aiResp.ValidationErrors,
		"validation_warnings": aiResp.ValidationWarnings,
		"pr_url":              aiResp.GitHubPRURL,
		"pr_number":           aiResp.GitHubPRNumber,
		"branch":              aiResp.GitHubBranch,
		"workflow_file":       aiResp.WorkflowFile,
		"workflow_run_id":     aiResp.WorkflowRunID,
	})
}

// POST /api/v1/repositories/:repoId/analyze
func (h *PipelineHandler) AnalyzeRepository(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	var repoFull struct {
		FullName             string
		AccessTokenEncrypted string
		ProjectID            uuid.UUID
	}
	h.db.Table("repositories").Select("full_name, access_token_encrypted, project_id").Where("id = ?", repoID).Scan(&repoFull)
	if repoFull.FullName == "" {
		c.JSON(http.StatusNotFound, gin.H{"error": "repository not found"})
		return
	}

	githubToken := ""
	if repoFull.AccessTokenEncrypted != "" {
		encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
		if len(encryptionKey) != 32 {
			fallback := make([]byte, 32)
			copy(fallback, "ai-devsecops-default-key-32bytes!")
			encryptionKey = fallback
		}
		decryptedToken, decryptErr := utils.DecryptAES(repoFull.AccessTokenEncrypted, encryptionKey)
		if decryptErr == nil {
			githubToken = decryptedToken
		}
	}

	aiResp, err := h.aiService.AnalyzeRepository(services.AnalyzeRequest{
		RepositoryID: repoID.String(),
		GitHubToken:  githubToken,
		ProjectID:    repoFull.ProjectID.String(),
	})
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("AI service error: %v", err)})
		return
	}

	h.db.Exec(`UPDATE repositories SET last_analyzed_at = NOW() WHERE id = ?`, repoID)

	techJSON, _ := json.Marshal(aiResp.Technologies)
	arch := ""
	if aiResp.Architecture != nil {
		if archStr, ok := aiResp.Architecture.(string); ok {
			arch = archStr
		}
	}

	hasDocker := false
	hasK8s := false
	hasTerraform := false
	if aiResp.Deployment != nil {
		if v, ok := aiResp.Deployment["docker"].(bool); ok {
			hasDocker = v
		}
		if v, ok := aiResp.Deployment["kubernetes"].(bool); ok {
			hasK8s = v
		}
		if v, ok := aiResp.Deployment["terraform"].(bool); ok {
			hasTerraform = v
		}
	}

	rawJSON, _ := json.Marshal(map[string]interface{}{
		"technologies":          aiResp.Technologies,
		"architecture":          aiResp.Architecture,
		"security_requirements": aiResp.SecurityNeeds,
		"existing_workflows":    aiResp.ExistingWorkflows,
		"deployment":            aiResp.Deployment,
	})

	h.db.Exec(`
		INSERT INTO repository_insights (
			id, repository_id, language, frameworks, build_tools, architecture_type,
			has_dockerfile, has_docker_compose, has_kubernetes, has_terraform,
			has_existing_ci_cd, existing_workflows, dependency_ecosystem, raw_analysis_output, last_updated
		)
		VALUES (gen_random_uuid(), ?, ?, '[]', '[]', ?, ?, false, ?, ?, false, '[]', '[]', ?::jsonb, NOW())
		ON CONFLICT (repository_id) DO UPDATE SET
			language = EXCLUDED.language,
			frameworks = EXCLUDED.frameworks,
			build_tools = EXCLUDED.build_tools,
			architecture_type = EXCLUDED.architecture_type,
			has_dockerfile = EXCLUDED.has_dockerfile,
			has_docker_compose = EXCLUDED.has_docker_compose,
			has_kubernetes = EXCLUDED.has_kubernetes,
			has_terraform = EXCLUDED.has_terraform,
			has_existing_ci_cd = EXCLUDED.has_existing_ci_cd,
			existing_workflows = EXCLUDED.existing_workflows,
			dependency_ecosystem = EXCLUDED.dependency_ecosystem,
			raw_analysis_output = EXCLUDED.raw_analysis_output,
			last_updated = NOW()
	`, repoID, string(techJSON), arch, hasDocker, hasK8s, hasTerraform, string(rawJSON))

	c.JSON(http.StatusOK, gin.H{
		"technologies":          aiResp.Technologies,
		"architecture":          aiResp.Architecture,
		"security_requirements": aiResp.SecurityNeeds,
		"existing_workflows":    aiResp.ExistingWorkflows,
		"errors":                aiResp.Errors,
	})
}

// DELETE /api/v1/repositories/:repoId/pipelines/:version
func (h *PipelineHandler) DeleteByVersion(c *gin.Context) {
	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	version, err := strconv.Atoi(c.Param("version"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid version number"})
		return
	}

	pipeline, err := h.pipelineRepo.FindByRepositoryAndVersion(repoID, version)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "pipeline version not found"})
		return
	}

	if err := h.pipelineRepo.Delete(pipeline.ID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "pipeline version deleted"})
}

// POST /api/v1/runs/:runId/cancel
func (h *PipelineHandler) CancelRun(c *gin.Context) {
	runID, err := uuid.Parse(c.Param("runId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid run id"})
		return
	}

	run, err := h.runRepo.FindByID(runID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "run not found"})
		return
	}

	if run.GitHubRunID == 0 || run.Pipeline.Repository.FullName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "no GitHub run ID associated with this run"})
		return
	}

	repo := run.Pipeline.Repository
	encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
	if len(encryptionKey) != 32 {
		fallback := make([]byte, 32)
		copy(fallback, "ai-devsecops-default-key-32bytes!")
		encryptionKey = fallback
	}
	decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey)
	if decryptErr != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to decrypt token"})
		return
	}

	svc := services.NewGitHubService()
	if err := svc.CancelWorkflowRun(decryptedToken, repo.FullName, run.GitHubRunID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to cancel workflow: %v", err)})
		return
	}

	run.Conclusion = models.RunConclusionCancelled
	h.runRepo.Update(run)

	c.JSON(http.StatusOK, gin.H{"message": "run cancelled"})
}

// marshalNodeIO serialises the AI service's per-node I/O trace
// into a JSON string suitable for the Pipeline.NodeIO jsonb column.
// Returns `"[]"` on any error so the column has a valid value even
// when the AI service didn't return a trace (older builds, or
// requests that bypassed the LLM stack). The trace carries each
// node's input keys, output diff, duration_ms, status, and (on
// failure) the error string — the FE renders this as a Tahap 1-3
// timeline analogous to the Tahap 4 cards in RunDetail.
func marshalNodeIO(records []map[string]any) string {
	if records == nil {
		return "[]"
	}
	b, err := json.Marshal(records)
	if err != nil {
		return "[]"
	}
	return string(b)
}
