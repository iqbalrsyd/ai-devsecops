package services

import (
	"encoding/hex"
	"errors"
	"fmt"

	"github.com/google/uuid"
	"github.com/user/ai-devsecops-backend/internal/config"
	"github.com/user/ai-devsecops-backend/internal/models"
	"github.com/user/ai-devsecops-backend/internal/repositories"
	"github.com/user/ai-devsecops-backend/internal/utils"
)

var (
	ErrRepositoryNotFound = errors.New("repository not found")
	ErrInvalidGitHubToken = errors.New("invalid GitHub token")
)

type RepositoryService struct {
	repoRepo    repositories.RepositoryRepository
	projectRepo repositories.ProjectRepository
	githubSvc   *GitHubService
	cfg         *config.Config
}

func NewRepositoryService(
	repoRepo repositories.RepositoryRepository,
	projectRepo repositories.ProjectRepository,
	githubSvc *GitHubService,
	cfg *config.Config,
) *RepositoryService {
	return &RepositoryService{repoRepo: repoRepo, projectRepo: projectRepo, githubSvc: githubSvc, cfg: cfg}
}

func (s *RepositoryService) Connect(projectID uuid.UUID, githubToken, fullName string) (*models.Repository, error) {
	if _, err := s.projectRepo.FindByID(projectID); err != nil {
		return nil, ErrProjectNotFound
	}

	if err := s.githubSvc.ValidateToken(githubToken); err != nil {
		return nil, fmt.Errorf("%w: %s", ErrInvalidGitHubToken, err.Error())
	}

	if err := s.githubSvc.CheckRepoAccess(githubToken, fullName); err != nil {
		return nil, fmt.Errorf("%w: %s", ErrInvalidGitHubToken, err.Error())
	}

	encryptionKey := s.encryptionKey()
	encrypted, err := utils.EncryptAES(githubToken, encryptionKey)
	if err != nil {
		return nil, err
	}

	repo := &models.Repository{
		ID:                   uuid.New(),
		ProjectID:            projectID,
		GithubID:             fullName,
		FullName:             fullName,
		DefaultBranch:        "main",
		AccessTokenEncrypted: encrypted,
	}

	if err := s.repoRepo.Create(repo); err != nil {
		return nil, err
	}

	return repo, nil
}

func (s *RepositoryService) GetByID(id uuid.UUID) (*models.Repository, error) {
	return s.repoRepo.FindByID(id)
}

func (s *RepositoryService) List(projectID uuid.UUID) ([]models.Repository, error) {
	if _, err := s.projectRepo.FindByID(projectID); err != nil {
		return nil, ErrProjectNotFound
	}
	return s.repoRepo.FindByProjectID(projectID)
}

func (s *RepositoryService) Delete(id uuid.UUID, userID uuid.UUID, role string) error {
	repo, err := s.repoRepo.FindByID(id)
	if err != nil {
		return ErrRepositoryNotFound
	}
	project, err := s.projectRepo.FindByID(repo.ProjectID)
	if err != nil {
		return ErrRepositoryNotFound
	}
	if project.UserID != userID && role != models.RoleAdmin {
		return ErrNotOwner
	}
	return s.repoRepo.Delete(id)
}

func (s *RepositoryService) DecryptToken(repo *models.Repository) (string, error) {
	key := s.encryptionKey()
	return utils.DecryptAES(repo.AccessTokenEncrypted, key)
}

type DecryptedRepo struct {
	Repo  *models.Repository
	Token string
}

func (s *RepositoryService) DecryptRepoToken(id uuid.UUID) (*DecryptedRepo, error) {
	repo, err := s.repoRepo.FindByID(id)
	if err != nil {
		return nil, ErrRepositoryNotFound
	}
	token, err := s.DecryptToken(repo)
	if err != nil {
		return nil, err
	}
	return &DecryptedRepo{Repo: repo, Token: token}, nil
}

func (s *RepositoryService) encryptionKey() []byte {
	key, _ := hex.DecodeString(s.cfg.EncryptionKey)
	if len(key) != 32 {
		fallback := make([]byte, 32)
		copy(fallback, "ai-devsecops-default-key-32bytes!")
		return fallback
	}
	return key
}
