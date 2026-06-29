package models

import (
	"time"

	"github.com/google/uuid"
)

type PipelineStatus string

const (
	PipelineStatusDraft     PipelineStatus = "draft"
	PipelineStatusGenerated PipelineStatus = "generated"
	PipelineStatusValidated PipelineStatus = "validated"
	PipelineStatusDeployed  PipelineStatus = "deployed"
	PipelineStatusFailed    PipelineStatus = "failed"
)

type Pipeline struct {
	ID                      uuid.UUID `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	RepositoryID            uuid.UUID `json:"repository_id" gorm:"type:uuid;not null;index"`
	VersionNumber           int       `json:"version_number" gorm:"not null"`
	Prompt                  string    `json:"prompt" gorm:"type:text;not null"`
	UserRequirements        string    `json:"user_requirements" gorm:"type:text"`
	GeneratedYAML           string    `json:"generated_yaml" gorm:"type:text;not null"`
	Stages                  string    `json:"stages" gorm:"type:jsonb;not null;default:'[]'"`
	AIExplanation           string    `json:"ai_explanation" gorm:"type:text"`
	GenerationParams        string    `json:"generation_params" gorm:"type:jsonb;not null;default:'{}'"`
	ValidationResults       string    `json:"validation_results" gorm:"type:jsonb"`
	DeploymentResults       string    `json:"deployment_results" gorm:"type:jsonb"`
	SecurityControlsApplied string    `json:"security_controls_applied" gorm:"type:jsonb;not null;default:'[]'"`
	ComplianceMetadata      string    `json:"compliance_metadata" gorm:"type:jsonb;not null;default:'{}'"`
	// NodeIO captures the per-node I/O trace (input keys, output
	// diff, duration_ms, status, error) for every node in Tahap 1-3
	// that ran when this pipeline version was generated. The AI
	// service already records this on the in-memory state — we
	// persist it here so the PipelineDetail page can render a Tahap
	// 1-3 timeline analogous to the Tahap 4 cards in RunDetail
	// (Bab 5.13.4: "Pipeline Detail page should expose the full
	// graph execution trace, not just the final YAML").
	NodeIO    string         `json:"node_io" gorm:"type:jsonb;not null;default:'[]'"`
	Status    PipelineStatus `json:"status" gorm:"default:draft;not null"`
	CreatedAt time.Time      `json:"created_at"`

	Repository Repository    `json:"repository,omitempty" gorm:"foreignKey:RepositoryID"`
	Runs       []PipelineRun `json:"runs,omitempty" gorm:"foreignKey:PipelineID"`
}
