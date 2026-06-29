package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type RepositoryInsightRepository interface {
	Create(insight *models.RepositoryInsight) error
	FindByRepository(repoID uuid.UUID) (*models.RepositoryInsight, error)
	Update(insight *models.RepositoryInsight) error
	Upsert(insight *models.RepositoryInsight) error
}

type repositoryInsightRepository struct {
	db *gorm.DB
}

func NewRepositoryInsightRepository(pdb *database.PostgresDB) RepositoryInsightRepository {
	return &repositoryInsightRepository{db: pdb.DB}
}

func (r *repositoryInsightRepository) Create(insight *models.RepositoryInsight) error {
	return r.db.Create(insight).Error
}

func (r *repositoryInsightRepository) FindByRepository(repoID uuid.UUID) (*models.RepositoryInsight, error) {
	var insight models.RepositoryInsight
	err := r.db.Where("repository_id = ?", repoID).First(&insight).Error
	if err != nil {
		return nil, err
	}
	return &insight, nil
}

func (r *repositoryInsightRepository) Update(insight *models.RepositoryInsight) error {
	return r.db.Save(insight).Error
}

func (r *repositoryInsightRepository) Upsert(insight *models.RepositoryInsight) error {
	return r.db.Where("repository_id = ?", insight.RepositoryID).Assign(insight).FirstOrCreate(insight).Error
}
