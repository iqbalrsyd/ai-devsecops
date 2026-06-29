package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type PipelineRepository interface {
	Create(pipeline *models.Pipeline) error
	FindByID(id uuid.UUID) (*models.Pipeline, error)
	FindByRepository(repoID uuid.UUID) ([]models.Pipeline, error)
	FindByRepositoryAndVersion(repoID uuid.UUID, version int) (*models.Pipeline, error)
	GetNextVersion(repoID uuid.UUID) (int, error)
	Update(pipeline *models.Pipeline) error
	Delete(id uuid.UUID) error
	ListAll(userID uuid.UUID, page, limit int, sortBy, sortOrder string) ([]models.Pipeline, int64, error)
}

type pipelineRepository struct {
	db *gorm.DB
}

func NewPipelineRepository(pdb *database.PostgresDB) PipelineRepository {
	return &pipelineRepository{db: pdb.DB}
}

func (r *pipelineRepository) Create(pipeline *models.Pipeline) error {
	return r.db.Create(pipeline).Error
}

func (r *pipelineRepository) FindByID(id uuid.UUID) (*models.Pipeline, error) {
	var pipeline models.Pipeline
	err := r.db.Preload("Repository").Preload("Runs").First(&pipeline, "id = ?", id).Error
	if err != nil {
		return nil, err
	}
	return &pipeline, nil
}

func (r *pipelineRepository) FindByRepository(repoID uuid.UUID) ([]models.Pipeline, error) {
	var pipelines []models.Pipeline
	err := r.db.Where("repository_id = ?", repoID).Order("version_number DESC").Find(&pipelines).Error
	return pipelines, err
}

func (r *pipelineRepository) FindByRepositoryAndVersion(repoID uuid.UUID, version int) (*models.Pipeline, error) {
	var pipeline models.Pipeline
	err := r.db.Preload("Repository").Preload("Runs").Where("repository_id = ? AND version_number = ?", repoID, version).First(&pipeline).Error
	if err != nil {
		return nil, err
	}
	return &pipeline, nil
}

func (r *pipelineRepository) GetNextVersion(repoID uuid.UUID) (int, error) {
	var maxVersion int
	err := r.db.Model(&models.Pipeline{}).Where("repository_id = ?", repoID).Select("COALESCE(MAX(version_number), 0)").Scan(&maxVersion).Error
	return maxVersion + 1, err
}

func (r *pipelineRepository) Update(pipeline *models.Pipeline) error {
	return r.db.Save(pipeline).Error
}

func (r *pipelineRepository) Delete(id uuid.UUID) error {
	return r.db.Delete(&models.Pipeline{}, "id = ?", id).Error
}

func (r *pipelineRepository) ListAll(userID uuid.UUID, page, limit int, sortBy, sortOrder string) ([]models.Pipeline, int64, error) {
	var pipelines []models.Pipeline
	var total int64

	query := r.db.Model(&models.Pipeline{}).
		Joins("JOIN repositories ON repositories.id = pipelines.repository_id").
		Joins("JOIN projects ON projects.id = repositories.project_id").
		Where("projects.user_id = ?", userID)

	query.Count(&total)

	orderClause := "pipelines.created_at DESC"
	if sortBy == "version_number" || sortBy == "risk_score" || sortBy == "compliance_score" {
		orderClause = "pipelines." + sortBy + " " + sortOrder
	}

	err := query.
		Preload("Repository").
		Preload("Repository.Project").
		Order(orderClause).
		Offset((page - 1) * limit).
		Limit(limit).
		Find(&pipelines).Error

	return pipelines, total, err
}
