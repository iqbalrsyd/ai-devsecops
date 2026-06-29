package services

import (
	"errors"

	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/models"
	"github.com/user/ai-devsecops-backend/internal/repositories"
)

var (
	ErrProjectNotFound = errors.New("project not found")
	ErrNotOwner        = errors.New("only the owner can delete this project")
)

type ProjectService struct {
	projectRepo repositories.ProjectRepository
	userRepo    repositories.UserRepository
}

func NewProjectService(projectRepo repositories.ProjectRepository, userRepo repositories.UserRepository) *ProjectService {
	return &ProjectService{projectRepo: projectRepo, userRepo: userRepo}
}

func (s *ProjectService) Create(userID uuid.UUID, name, description string) (*models.Project, error) {
	project := &models.Project{
		ID:          uuid.New(),
		Name:        name,
		Description: description,
		UserID:      userID,
	}
	if err := s.projectRepo.Create(project); err != nil {
		return nil, err
	}
	return project, nil
}

func (s *ProjectService) List(userID uuid.UUID) ([]models.Project, error) {
	return s.projectRepo.FindByUserID(userID)
}

func (s *ProjectService) GetByID(id uuid.UUID) (*models.Project, error) {
	project, err := s.projectRepo.FindByID(id)
	if err != nil {
		return nil, ErrProjectNotFound
	}
	return project, nil
}

func (s *ProjectService) UpdateComplianceTier(projectID uuid.UUID, userID uuid.UUID, tier string) error {
	project, err := s.projectRepo.FindByID(projectID)
	if err != nil {
		return ErrProjectNotFound
	}
	if project.UserID != userID {
		return ErrNotOwner
	}
	return s.projectRepo.UpdateComplianceTier(projectID, tier)
}

func (s *ProjectService) Delete(projectID uuid.UUID, userID uuid.UUID, role string) error {
	project, err := s.projectRepo.FindByID(projectID)
	if err != nil {
		return ErrProjectNotFound
	}
	if project.UserID != userID && role != models.RoleAdmin {
		return ErrNotOwner
	}
	return s.projectRepo.SoftDelete(projectID)
}
