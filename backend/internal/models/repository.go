package models

import (
	"time"

	"github.com/google/uuid"
)

type Repository struct {
	ID                   uuid.UUID  `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	ProjectID            uuid.UUID  `json:"project_id" gorm:"type:uuid;not null;index"`
	GithubID             string     `json:"github_id" gorm:"not null"`
	FullName             string     `json:"full_name" gorm:"not null"`
	DefaultBranch        string     `json:"default_branch"`
	AccessTokenEncrypted string     `json:"-" gorm:"type:text"`
	LastSyncedAt         *time.Time `json:"last_synced_at"`
	LastAnalyzedAt       *time.Time `json:"last_analyzed_at"`
	CreatedAt            time.Time  `json:"created_at"`
	UpdatedAt            time.Time  `json:"updated_at"`

	Project   Project            `json:"-" gorm:"foreignKey:ProjectID"`
	Insight   *RepositoryInsight `json:"insight,omitempty" gorm:"foreignKey:RepositoryID"`
	Pipelines []Pipeline         `json:"pipelines,omitempty" gorm:"foreignKey:RepositoryID"`
}
