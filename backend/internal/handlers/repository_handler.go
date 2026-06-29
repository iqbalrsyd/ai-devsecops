package handlers

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/user/ai-devsecops-backend/internal/services"
)

type RepositoryHandler struct {
	repositoryService *services.RepositoryService
}

func NewRepositoryHandler(repositoryService *services.RepositoryService) *RepositoryHandler {
	return &RepositoryHandler{repositoryService: repositoryService}
}

type connectRepositoryRequest struct {
	ProjectID   string `json:"project_id" binding:"required"`
	GithubToken string `json:"github_token" binding:"required"`
	FullName    string `json:"full_name" binding:"required"`
}

func (h *RepositoryHandler) Connect(c *gin.Context) {
	var req connectRepositoryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	projectID, err := uuid.Parse(req.ProjectID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid project_id"})
		return
	}

	repo, err := h.repositoryService.Connect(projectID, req.GithubToken, req.FullName)
	if err != nil {
		status := http.StatusInternalServerError
		if err == services.ErrProjectNotFound {
			status = http.StatusNotFound
		} else if errors.Is(err, services.ErrInvalidGitHubToken) {
			status = http.StatusUnauthorized
		}
		c.JSON(status, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusCreated, gin.H{"repository": repo})
}

func (h *RepositoryHandler) ListByProject(c *gin.Context) {
	projectID, err := uuid.Parse(c.Param("projectId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid project id"})
		return
	}

	repos, err := h.repositoryService.List(projectID)
	if err != nil {
		status := http.StatusInternalServerError
		if err == services.ErrProjectNotFound {
			status = http.StatusNotFound
		}
		c.JSON(status, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"repositories": repos})
}

func (h *RepositoryHandler) GetByID(c *gin.Context) {
	id, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	repo, err := h.repositoryService.GetByID(id)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "repository not found"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"repository": repo})
}

func (h *RepositoryHandler) Delete(c *gin.Context) {
	userIDStr, _ := c.Get("userID")
	userID, _ := uuid.Parse(userIDStr.(string))
	role, _ := c.Get("role")

	repoID, err := uuid.Parse(c.Param("repoId"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid repository id"})
		return
	}

	if err := h.repositoryService.Delete(repoID, userID, role.(string)); err != nil {
		status := http.StatusInternalServerError
		if err == services.ErrRepositoryNotFound {
			status = http.StatusNotFound
		} else if err == services.ErrNotOwner {
			status = http.StatusForbidden
		}
		c.JSON(status, gin.H{"error": err.Error()})
		return
	}
	c.JSON(http.StatusOK, gin.H{"message": "repository deleted"})
}
