package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type RepositoryRepository interface {
	Create(repo *models.Repository) error
	FindByProjectID(projectID uuid.UUID) ([]models.Repository, error)
	FindByID(id uuid.UUID) (*models.Repository, error)
	Delete(id uuid.UUID) error
}

type repositoryRepository struct {
	db *gorm.DB
}

func NewRepositoryRepository(pdb *database.PostgresDB) RepositoryRepository {
	return &repositoryRepository{db: pdb.DB}
}

func (r *repositoryRepository) Create(repo *models.Repository) error {
	return r.db.Create(repo).Error
}

func (r *repositoryRepository) FindByProjectID(projectID uuid.UUID) ([]models.Repository, error) {
	var repos []models.Repository
	err := r.db.Where("project_id = ?", projectID).Find(&repos).Error
	return repos, err
}

func (r *repositoryRepository) FindByID(id uuid.UUID) (*models.Repository, error) {
	var repo models.Repository
	err := r.db.First(&repo, "id = ?", id).Error
	if err != nil {
		return nil, err
	}
	return &repo, nil
}

func (r *repositoryRepository) Delete(id uuid.UUID) error {
	return r.db.Delete(&models.Repository{}, "id = ?", id).Error
}
