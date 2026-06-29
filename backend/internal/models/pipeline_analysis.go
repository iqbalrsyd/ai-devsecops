package models

import (
	"time"

	"github.com/google/uuid"
)

type PipelineAnalysis struct {
	ID                    uuid.UUID `json:"id" gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	PipelineRunID         uuid.UUID `json:"pipeline_run_id" gorm:"type:uuid;not null;uniqueIndex"`
	RiskScore             float64   `json:"risk_score" gorm:"type:decimal(5,2)"`
	ComplianceScore       float64   `json:"compliance_score" gorm:"type:decimal(5,2)"`
	WorkflowQualityScore  float64   `json:"workflow_quality_score" gorm:"type:decimal(5,2)"`
	SecurityCoverageScore float64   `json:"security_coverage_score" gorm:"type:decimal(5,2)"`
	FindingsSummary       string    `json:"findings_summary" gorm:"type:jsonb"`
	SeverityBreakdown     string    `json:"severity_breakdown" gorm:"type:jsonb;default:'{}'"`
	Recommendations       string    `json:"recommendations" gorm:"type:jsonb;default:'[]'"`
	AIExplanation         string    `json:"ai_explanation" gorm:"type:text"`
	RawScanData           string    `json:"raw_scan_data" gorm:"type:jsonb"`
	CreatedAt             time.Time `json:"created_at"`

	PipelineRun PipelineRun `json:"pipeline_run,omitempty" gorm:"foreignKey:PipelineRunID"`
}
