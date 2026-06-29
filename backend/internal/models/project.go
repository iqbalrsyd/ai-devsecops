package models

import (
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

type Project struct {
	ID             uuid.UUID      `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	Name           string         `json:"name" gorm:"not null"`
	Description    string         `json:"description" gorm:"type:text"`
	UserID         uuid.UUID      `json:"user_id" gorm:"type:uuid;not null;index"`
	ComplianceTier string         `json:"compliance_tier" gorm:"type:varchar(20);default:moderate"`
	CreatedAt      time.Time      `json:"created_at"`
	UpdatedAt      time.Time      `json:"updated_at"`
	DeletedAt      gorm.DeletedAt `json:"-" gorm:"index"`

	User User `json:"-" gorm:"foreignKey:UserID"`
}
