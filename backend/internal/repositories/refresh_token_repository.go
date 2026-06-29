package repositories

import (
	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/models"
	"gorm.io/gorm"
)

type RefreshTokenRepository interface {
	FindByToken(token string) (*models.RefreshToken, error)
	FindByUserID(userID uuid.UUID) ([]models.RefreshToken, error)
	Create(token *models.RefreshToken) error
	Delete(id uuid.UUID) error
	DeleteByUserID(userID uuid.UUID) error
}

type refreshTokenRepository struct {
	db *gorm.DB
}

func NewRefreshTokenRepository(pdb *database.PostgresDB) RefreshTokenRepository {
	return &refreshTokenRepository{db: pdb.DB}
}

func (r *refreshTokenRepository) FindByToken(token string) (*models.RefreshToken, error) {
	var t models.RefreshToken
	err := r.db.Where("token = ?", token).First(&t).Error
	if err != nil {
		return nil, err
	}
	return &t, nil
}

func (r *refreshTokenRepository) FindByUserID(userID uuid.UUID) ([]models.RefreshToken, error) {
	var tokens []models.RefreshToken
	err := r.db.Where("user_id = ?", userID).Find(&tokens).Error
	return tokens, err
}

func (r *refreshTokenRepository) Create(token *models.RefreshToken) error {
	return r.db.Create(token).Error
}

func (r *refreshTokenRepository) Delete(id uuid.UUID) error {
	return r.db.Delete(&models.RefreshToken{}, "id = ?", id).Error
}

func (r *refreshTokenRepository) DeleteByUserID(userID uuid.UUID) error {
	return r.db.Delete(&models.RefreshToken{}, "user_id = ?", userID).Error
}
