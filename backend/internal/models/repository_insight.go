package models

import (
	"time"

	"github.com/google/uuid"
)

type RepositoryInsight struct {
	ID                  uuid.UUID  `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	RepositoryID        uuid.UUID  `json:"repository_id" gorm:"type:uuid;not null;uniqueIndex"`
	PrimaryLanguage     string     `json:"primary_language" gorm:"type:varchar(100)"`
	SecondaryLanguages  string     `json:"secondary_languages" gorm:"type:jsonb;default:'[]'"`
	Frameworks          string     `json:"frameworks" gorm:"type:jsonb;default:'[]'"`
	BuildTools          string     `json:"build_tools" gorm:"type:jsonb;default:'[]'"`
	PackageManagers     string     `json:"package_managers" gorm:"type:jsonb;default:'[]'"`
	TestFrameworks      string     `json:"test_frameworks" gorm:"type:jsonb;default:'[]'"`
	ArchitectureType    string     `json:"architecture_type" gorm:"type:varchar(50)"`
	HasDockerfile       bool       `json:"has_dockerfile" gorm:"default:false"`
	HasDockerCompose    bool       `json:"has_docker_compose" gorm:"default:false"`
	HasKubernetes       bool       `json:"has_kubernetes" gorm:"default:false"`
	HasTerraform        bool       `json:"has_terraform" gorm:"default:false"`
	HasExistingCICD     bool       `json:"has_existing_ci_cd" gorm:"default:false"`
	ExistingWorkflows   string     `json:"existing_workflows" gorm:"type:jsonb;default:'[]'"`
	DependencyEcosystem string     `json:"dependency_ecosystem" gorm:"type:jsonb;default:'[]'"`
	RawAnalysisOutput   string     `json:"raw_analysis_output" gorm:"type:jsonb"`
	AnalyzedAt          *time.Time `json:"analyzed_at"`
	CreatedAt           time.Time  `json:"created_at"`
	UpdatedAt           time.Time  `json:"updated_at"`

	Repository Repository `json:"repository,omitempty" gorm:"foreignKey:RepositoryID"`
}
