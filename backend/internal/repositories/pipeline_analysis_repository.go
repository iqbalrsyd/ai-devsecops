package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type PipelineAnalysisRepository interface {
	Create(analysis *models.PipelineAnalysis) error
	FindByRunID(runID uuid.UUID) (*models.PipelineAnalysis, error)
	FindByPipelineID(pipelineID uuid.UUID) ([]models.PipelineAnalysis, error)
}

type pipelineAnalysisRepository struct {
	db *gorm.DB
}

func NewPipelineAnalysisRepository(pdb *database.PostgresDB) PipelineAnalysisRepository {
	return &pipelineAnalysisRepository{db: pdb.DB}
}

func (r *pipelineAnalysisRepository) Create(analysis *models.PipelineAnalysis) error {
	return r.db.Create(analysis).Error
}

func (r *pipelineAnalysisRepository) FindByRunID(runID uuid.UUID) (*models.PipelineAnalysis, error) {
	var analysis models.PipelineAnalysis
	err := r.db.Preload("PipelineRun").First(&analysis, "pipeline_run_id = ?", runID).Error
	if err != nil {
		return nil, err
	}
	return &analysis, nil
}

func (r *pipelineAnalysisRepository) FindByPipelineID(pipelineID uuid.UUID) ([]models.PipelineAnalysis, error) {
	var analyses []models.PipelineAnalysis
	err := r.db.
		Joins("JOIN pipeline_runs ON pipeline_runs.id = pipeline_analyses.pipeline_run_id").
		Where("pipeline_runs.pipeline_id = ?", pipelineID).
		Order("pipeline_analyses.created_at DESC").
		Find(&analyses).Error
	return analyses, err
}
