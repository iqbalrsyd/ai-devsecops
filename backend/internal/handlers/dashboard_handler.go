package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"gorm.io/gorm"
)

type DashboardHandler struct {
	db *gorm.DB
}

func NewDashboardHandler(db *gorm.DB) *DashboardHandler {
	return &DashboardHandler{db: db}
}

type PipelineSummary struct {
	ID         string `json:"id"`
	Version    int    `json:"version"`
	Repository string `json:"repository"`
	Status     string `json:"status"`
	CreatedAt  string `json:"created_at"`
}

type DashboardStats struct {
	TotalProjects       int64             `json:"total_projects"`
	TotalRepositories   int64             `json:"total_repositories"`
	TotalPipelines      int64             `json:"total_pipelines"`
	TotalExecutions     int64             `json:"total_executions"`
	PipelineSuccessRate float64           `json:"pipeline_success_rate"`
	AvgRiskScore        float64           `json:"avg_risk_score"`
	AvgComplianceScore  float64           `json:"avg_compliance_score"`
	AvgSecurityCoverage float64           `json:"avg_security_coverage"`
	AvgWorkflowQuality  float64           `json:"avg_workflow_quality"`
	RecentPipelines     []PipelineSummary `json:"recent_pipelines"`
}

func (h *DashboardHandler) Stats(c *gin.Context) {
	userIDStr, _ := c.Get("userID")
	userID, err := uuid.Parse(userIDStr.(string))
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid user"})
		return
	}

	var stats DashboardStats

	h.db.Table("projects").
		Where("user_id = ?", userID).
		Count(&stats.TotalProjects)

	h.db.Table("repositories").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Count(&stats.TotalRepositories)

	h.db.Table("pipelines").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Count(&stats.TotalPipelines)

	h.db.Table("pipeline_runs").
		Joins("JOIN pipelines ON pipelines.id = pipeline_runs.pipeline_id").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Count(&stats.TotalExecutions)

	h.db.Table("pipeline_runs").
		Select("COALESCE((COUNT(CASE WHEN conclusion = 'success' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN conclusion IS NOT NULL THEN 1 END), 0)), 0)").
		Joins("JOIN pipelines ON pipelines.id = pipeline_runs.pipeline_id").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Scan(&stats.PipelineSuccessRate)

	h.db.Table("pipeline_analyses").
		Select("COALESCE(AVG(risk_score), 0)").
		Joins("JOIN pipeline_runs ON pipeline_runs.id = pipeline_analyses.pipeline_run_id").
		Joins("JOIN pipelines ON pipelines.id = pipeline_runs.pipeline_id").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Scan(&stats.AvgRiskScore)

	h.db.Table("pipeline_analyses").
		Select("COALESCE(AVG(compliance_score), 0)").
		Joins("JOIN pipeline_runs ON pipeline_runs.id = pipeline_analyses.pipeline_run_id").
		Joins("JOIN pipelines ON pipelines.id = pipeline_runs.pipeline_id").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Scan(&stats.AvgComplianceScore)

	h.db.Table("pipeline_analyses").
		Select("COALESCE(AVG(security_coverage_score), 0)").
		Joins("JOIN pipeline_runs ON pipeline_runs.id = pipeline_analyses.pipeline_run_id").
		Joins("JOIN pipelines ON pipelines.id = pipeline_runs.pipeline_id").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Scan(&stats.AvgSecurityCoverage)

	h.db.Table("pipeline_analyses").
		Select("COALESCE(AVG(workflow_quality_score), 0)").
		Joins("JOIN pipeline_runs ON pipeline_runs.id = pipeline_analyses.pipeline_run_id").
		Joins("JOIN pipelines ON pipelines.id = pipeline_runs.pipeline_id").
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Scan(&stats.AvgWorkflowQuality)

	var recent []PipelineSummary
	h.db.Table("pipelines").
		Select(`
			pipelines.id,
			pipelines.version_number as version,
			repositories.full_name as repository,
			pipelines.status,
			pipelines.created_at
		`).
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID).
		Order("pipelines.created_at DESC").
		Limit(10).
		Scan(&recent)

	stats.RecentPipelines = recent

	c.JSON(http.StatusOK, stats)
}
