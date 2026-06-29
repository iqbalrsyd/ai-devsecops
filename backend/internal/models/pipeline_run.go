package models

import (
	"time"

	"github.com/google/uuid"
)

type RunStatus string

const (
	RunStatusPending   RunStatus = "pending"
	RunStatusQueued    RunStatus = "queued"
	RunStatusRunning   RunStatus = "running"
	RunStatusCompleted RunStatus = "completed"
	RunStatusFailed    RunStatus = "failed"
)

type RunConclusion string

const (
	RunConclusionSuccess   RunConclusion = "success"
	RunConclusionFailure   RunConclusion = "failure"
	RunConclusionCancelled RunConclusion = "cancelled"
	RunConclusionSkipped   RunConclusion = "skipped"
)

type PipelineRun struct {
	ID              uuid.UUID     `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	PipelineID      uuid.UUID     `json:"pipeline_id" gorm:"type:uuid;not null;index"`
	RunNumber       int           `json:"run_number" gorm:"not null"`
	GitHubRunID     int64         `json:"github_run_id"`
	Status          RunStatus     `json:"status" gorm:"default:pending"`
	Conclusion      RunConclusion `json:"conclusion"`
	HTMLURL         string        `json:"html_url" gorm:"type:text"`
	StartedAt       *time.Time    `json:"started_at"`
	CompletedAt     *time.Time    `json:"completed_at"`
	DurationSeconds int           `json:"duration_seconds"`
	Jobs            string        `json:"jobs" gorm:"type:jsonb"`
	LogsURL         string        `json:"logs_url" gorm:"type:text"`
	ErrorMessage    string        `json:"error_message" gorm:"type:text"`
	CreatedAt       time.Time     `json:"created_at"`

	Pipeline Pipeline `json:"pipeline,omitempty" gorm:"foreignKey:PipelineID"`
}
