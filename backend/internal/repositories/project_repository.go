package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type ProjectRepository interface {
	Create(project *models.Project) error
	FindByUserID(userID uuid.UUID) ([]models.Project, error)
	FindByID(id uuid.UUID) (*models.Project, error)
	SoftDelete(id uuid.UUID) error
	UpdateComplianceTier(id uuid.UUID, tier string) error
}

type projectRepository struct {
	db *gorm.DB
}

func NewProjectRepository(pdb *database.PostgresDB) ProjectRepository {
	return &projectRepository{db: pdb.DB}
}

func (r *projectRepository) Create(project *models.Project) error {
	return r.db.Create(project).Error
}

func (r *projectRepository) FindByUserID(userID uuid.UUID) ([]models.Project, error) {
	var projects []models.Project
	err := r.db.Where("user_id = ?", userID).Find(&projects).Error
	return projects, err
}

func (r *projectRepository) FindByID(id uuid.UUID) (*models.Project, error) {
	var project models.Project
	err := r.db.First(&project, "id = ?", id).Error
	if err != nil {
		return nil, err
	}
	return &project, nil
}

func (r *projectRepository) UpdateComplianceTier(id uuid.UUID, tier string) error {
	return r.db.Model(&models.Project{}).Where("id = ?", id).Update("compliance_tier", tier).Error
}

func (r *projectRepository) SoftDelete(id uuid.UUID) error {
	return r.db.Transaction(func(tx *gorm.DB) error {
		subPipelineAnalysis := tx.Where(
			"pipeline_run_id IN (SELECT id FROM pipeline_runs WHERE pipeline_id IN (SELECT id FROM pipelines WHERE repository_id IN (SELECT id FROM repositories WHERE project_id = ?)))",
			id,
		)
		if err := subPipelineAnalysis.Delete(&models.PipelineAnalysis{}).Error; err != nil {
			return err
		}

		subPipelineRun := tx.Where(
			"pipeline_id IN (SELECT id FROM pipelines WHERE repository_id IN (SELECT id FROM repositories WHERE project_id = ?))",
			id,
		)
		if err := subPipelineRun.Delete(&models.PipelineRun{}).Error; err != nil {
			return err
		}

		subPipeline := tx.Where(
			"repository_id IN (SELECT id FROM repositories WHERE project_id = ?)",
			id,
		)
		if err := subPipeline.Delete(&models.Pipeline{}).Error; err != nil {
			return err
		}

		subInsight := tx.Where("repository_id IN (SELECT id FROM repositories WHERE project_id = ?)", id)
		if err := subInsight.Delete(&models.RepositoryInsight{}).Error; err != nil {
			return err
		}

		subRepo := tx.Where("project_id = ?", id)
		if err := subRepo.Delete(&models.Repository{}).Error; err != nil {
			return err
		}

		return tx.Delete(&models.Project{}, "id = ?", id).Error
	})
}
