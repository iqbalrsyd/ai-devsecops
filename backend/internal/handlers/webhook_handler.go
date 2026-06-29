package handlers

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/user/ai-devsecops-backend/internal/config"
	"github.com/user/ai-devsecops-backend/internal/models"
	"github.com/user/ai-devsecops-backend/internal/repositories"
	"github.com/user/ai-devsecops-backend/internal/services"
	"github.com/user/ai-devsecops-backend/internal/utils"
	"gorm.io/gorm"
)

type WebhookHandler struct {
	db           *gorm.DB
	pipelineRepo repositories.PipelineRepository
	runRepo      repositories.PipelineRunRepository
	analysisRepo repositories.PipelineAnalysisRepository
	cfg          *config.Config
}

func NewWebhookHandler(
	db *gorm.DB,
	pipelineRepo repositories.PipelineRepository,
	runRepo repositories.PipelineRunRepository,
	analysisRepo repositories.PipelineAnalysisRepository,
	cfg *config.Config,
) *WebhookHandler {
	return &WebhookHandler{db: db, pipelineRepo: pipelineRepo, runRepo: runRepo, analysisRepo: analysisRepo, cfg: cfg}
}

type workflowRunEvent struct {
	Action      string `json:"action"`
	WorkflowRun *struct {
		ID         int64  `json:"id"`
		Status     string `json:"status"`
		Conclusion string `json:"conclusion"`
		HTMLURL    string `json:"html_url"`
		HeadBranch string `json:"head_branch"`
		RunNumber  int    `json:"run_number"`
		CreatedAt  string `json:"created_at"`
		UpdatedAt  string `json:"updated_at"`
	} `json:"workflow_run"`
	Workflow *struct {
		ID   int64  `json:"id"`
		Name string `json:"name"`
		Path string `json:"path"`
	} `json:"workflow"`
	Repository *struct {
		FullName string `json:"full_name"`
		ID       int64  `json:"id"`
	} `json:"repository"`
}

type pushEvent struct {
	Ref        string `json:"ref"`
	Repository *struct {
		FullName string `json:"full_name"`
		ID       int64  `json:"id"`
	} `json:"repository"`
}

func (h *WebhookHandler) HandleGitHubWebhook(c *gin.Context) {
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to read body"})
		return
	}

	eventType := c.GetHeader("X-GitHub-Event")
	if eventType == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing X-GitHub-Event header"})
		return
	}

	switch eventType {
	case "workflow_run":
		h.handleWorkflowRun(c, body)
	case "push":
		h.handlePush(c, body)
	case "ping":
		c.JSON(http.StatusOK, gin.H{"message": "pong"})
	default:
		c.JSON(http.StatusOK, gin.H{"message": "event ignored"})
	}
}

func (h *WebhookHandler) handleWorkflowRun(c *gin.Context, body []byte) {
	var event workflowRunEvent
	if err := json.Unmarshal(body, &event); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid payload"})
		return
	}

	if event.WorkflowRun == nil || event.Repository == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing workflow_run or repository"})
		return
	}

	fullName := event.Repository.FullName
	ghRunID := event.WorkflowRun.ID
	status := event.WorkflowRun.Status
	conclusion := event.WorkflowRun.Conclusion
	htmlURL := event.WorkflowRun.HTMLURL
	runNumber := event.WorkflowRun.RunNumber

	var repo models.Repository
	if err := h.db.Where("full_name = ?", fullName).First(&repo).Error; err != nil {
		c.JSON(http.StatusOK, gin.H{"message": "repository not found, skipping"})
		return
	}

	pipelines, err := h.pipelineRepo.FindByRepository(repo.ID)
	if err != nil || len(pipelines) == 0 {
		c.JSON(http.StatusOK, gin.H{"message": "no pipeline found for repository, skipping"})
		return
	}

	workflowPath := ""
	if event.Workflow != nil {
		workflowPath = event.Workflow.Path
	}

	var pipeline *models.Pipeline
	if workflowPath != "" {
		for _, p := range pipelines {
			if p.DeploymentResults != "" && p.DeploymentResults != "null" {
				var depInfo struct {
					WorkflowFile string `json:"workflow_file"`
				}
				if err := json.Unmarshal([]byte(p.DeploymentResults), &depInfo); err == nil && depInfo.WorkflowFile == workflowPath {
					pipeline = &p
					break
				}
			}
		}
	}

	if pipeline == nil {
		pipeline = &pipelines[0]
		fmt.Printf("[Webhook] No workflow match for '%s', using latest pipeline %d\n", workflowPath, pipeline.VersionNumber)
	} else {
		fmt.Printf("[Webhook] Matched workflow '%s' to pipeline v%d\n", workflowPath, pipeline.VersionNumber)
	}

	var existingRun models.PipelineRun
	result := h.db.Where("pipeline_id = ? AND github_run_id = ?", pipeline.ID, ghRunID).First(&existingRun)

	runStatus := mapStatus(status)
	runConclusion := mapConclusion(conclusion)

	var run *models.PipelineRun

	if result.Error != nil {
		run = &models.PipelineRun{
			PipelineID:  pipeline.ID,
			RunNumber:   runNumber,
			GitHubRunID: ghRunID,
			Status:      runStatus,
			Conclusion:  runConclusion,
			HTMLURL:     htmlURL,
		}
		if err := h.runRepo.Create(run); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create run"})
			return
		}
	} else {
		run = &existingRun
		run.Status = runStatus
		run.Conclusion = runConclusion
		run.HTMLURL = htmlURL
	}

	// Fetch jobs from GitHub if workflow completed
	if status == "completed" && repo.AccessTokenEncrypted != "" {
		encryptionKey, _ := hex.DecodeString(h.cfg.EncryptionKey)
		if len(encryptionKey) != 32 {
			fallback := make([]byte, 32)
			copy(fallback, "ai-devsecops-default-key-32bytes!")
			encryptionKey = fallback
		}
		if decryptedToken, decryptErr := utils.DecryptAES(repo.AccessTokenEncrypted, encryptionKey); decryptErr == nil {
			svc := services.NewGitHubService()
			if ghJobs, jobErr := svc.GetWorkflowRunJobs(decryptedToken, fullName, ghRunID); jobErr == nil && len(ghJobs) > 0 {
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
				if bytes, marshalErr := json.Marshal(mapped); marshalErr == nil {
					run.Jobs = string(bytes)
				}
			}
		}
	}

	if err := h.runRepo.Update(run); err != nil {
		fmt.Printf("[Webhook] Failed to update run: %v\n", err)
	}

	if status == "completed" && run.Jobs != "" && run.Jobs != "null" {
		// The webhook path has no AI service / GitHub token in scope,
		// so we pass nil + empty strings. createAnalysisFromJobs treats
		// a nil aiService as "skip the AI step" and uses the raw jobs
		// (already populated above) plus any available annotations.
		createAnalysisFromJobs(h.db, h.analysisRepo, nil, run, "", "")
	}

	c.JSON(http.StatusOK, gin.H{"message": "ok"})
}

func (h *WebhookHandler) handlePush(c *gin.Context, body []byte) {
	var event pushEvent
	if err := json.Unmarshal(body, &event); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid payload"})
		return
	}

	if event.Repository == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing repository"})
		return
	}

	var repo models.Repository
	if err := h.db.Where("full_name = ?", event.Repository.FullName).First(&repo).Error; err != nil {
		c.JSON(http.StatusOK, gin.H{"message": "repository not found, skipping"})
		return
	}

	fmt.Printf("Push event received for repository: %s\n", event.Repository.FullName)
	c.JSON(http.StatusOK, gin.H{"message": "ok"})
}

func mapStatus(status string) models.RunStatus {
	switch status {
	case "queued":
		return models.RunStatusQueued
	case "in_progress":
		return models.RunStatusRunning
	case "completed":
		return models.RunStatusCompleted
	case "waiting":
		return models.RunStatusQueued
	case "pending":
		return models.RunStatusPending
	default:
		return models.RunStatusPending
	}
}

func mapConclusion(conclusion string) models.RunConclusion {
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
