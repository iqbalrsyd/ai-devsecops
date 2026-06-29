package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type PipelineRunRepository interface {
	Create(run *models.PipelineRun) error
	FindByID(id uuid.UUID) (*models.PipelineRun, error)
	FindByPipeline(pipelineID uuid.UUID) ([]models.PipelineRun, error)
	FindByPipelineAndRunNumber(pipelineID uuid.UUID, runNumber int) (*models.PipelineRun, error)
	GetNextRunNumber(pipelineID uuid.UUID) (int, error)
	Update(run *models.PipelineRun) error
}

type pipelineRunRepository struct {
	db *gorm.DB
}

func NewPipelineRunRepository(pdb *database.PostgresDB) PipelineRunRepository {
	return &pipelineRunRepository{db: pdb.DB}
}

func (r *pipelineRunRepository) Create(run *models.PipelineRun) error {
	return r.db.Create(run).Error
}

func (r *pipelineRunRepository) FindByID(id uuid.UUID) (*models.PipelineRun, error) {
	var run models.PipelineRun
	err := r.db.Preload("Pipeline").Preload("Pipeline.Repository").First(&run, "id = ?", id).Error
	if err != nil {
		return nil, err
	}
	return &run, nil
}

func (r *pipelineRunRepository) FindByPipeline(pipelineID uuid.UUID) ([]models.PipelineRun, error) {
	var runs []models.PipelineRun
	err := r.db.Where("pipeline_id = ?", pipelineID).Order("run_number DESC").Find(&runs).Error
	return runs, err
}

func (r *pipelineRunRepository) FindByPipelineAndRunNumber(pipelineID uuid.UUID, runNumber int) (*models.PipelineRun, error) {
	var run models.PipelineRun
	err := r.db.Where("pipeline_id = ? AND run_number = ?", pipelineID, runNumber).First(&run).Error
	if err != nil {
		return nil, err
	}
	return &run, nil
}

func (r *pipelineRunRepository) GetNextRunNumber(pipelineID uuid.UUID) (int, error) {
	var maxRun int
	err := r.db.Model(&models.PipelineRun{}).Where("pipeline_id = ?", pipelineID).Select("COALESCE(MAX(run_number), 0)").Scan(&maxRun).Error
	return maxRun + 1, err
}

func (r *pipelineRunRepository) Update(run *models.PipelineRun) error {
	return r.db.Save(run).Error
}
