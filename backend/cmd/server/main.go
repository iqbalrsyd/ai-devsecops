package main

import (
	"fmt"
	"log"

	"github.com/gin-gonic/gin"
	"github.com/user/ai-devsecops-backend/internal/config"
	"github.com/user/ai-devsecops-backend/internal/database"
	"github.com/user/ai-devsecops-backend/internal/handlers"
	"github.com/user/ai-devsecops-backend/internal/middleware"
	"github.com/user/ai-devsecops-backend/internal/models"
	"github.com/user/ai-devsecops-backend/internal/repositories"
	"github.com/user/ai-devsecops-backend/internal/services"
	"go.uber.org/zap"
)

func main() {
	logger, err := zap.NewProduction()
	if err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}
	defer logger.Sync()

	cfg, err := config.Load()
	if err != nil {
		logger.Fatal("Failed to load config", zap.Error(err))
	}

	postgresDB, err := database.NewPostgresConnection(cfg)
	if err != nil {
		logger.Fatal("Failed to connect to PostgreSQL", zap.Error(err))
	}
	defer postgresDB.Close()

	if err := postgresDB.AutoMigrate(
		&models.User{},
		&models.RefreshToken{},
		&models.Project{},
		&models.Repository{},
		&models.RepositoryInsight{},
		&models.Pipeline{},
		&models.PipelineRun{},
		&models.PipelineAnalysis{},
	); err != nil {
		logger.Fatal("Failed to auto-migrate database", zap.Error(err))
	}
	logger.Info("Database migration completed successfully")

	redisDB, err := database.NewRedisConnection(cfg)
	if err != nil {
		logger.Fatal("Failed to connect to Redis", zap.Error(err))
	}
	defer redisDB.Close()

	userRepo := repositories.NewUserRepository(postgresDB)
	projectRepo := repositories.NewProjectRepository(postgresDB)
	repoRepo := repositories.NewRepositoryRepository(postgresDB)
	pipelineRepo := repositories.NewPipelineRepository(postgresDB)
	runRepo := repositories.NewPipelineRunRepository(postgresDB)
	analysisRepo := repositories.NewPipelineAnalysisRepository(postgresDB)
	insightRepo := repositories.NewRepositoryInsightRepository(postgresDB)

	refreshTokenRepo := repositories.NewRefreshTokenRepository(postgresDB)
	authService := services.NewAuthService(userRepo, refreshTokenRepo, cfg)
	projectService := services.NewProjectService(projectRepo, userRepo)
	githubClient := services.NewGitHubService()
	repositoryService := services.NewRepositoryService(repoRepo, projectRepo, githubClient, cfg)
	aiService := services.NewAIService(cfg.AIServiceURL())

	router := gin.New()

	router.Use(middleware.CORS())
	router.Use(middleware.Logger(logger))
	router.Use(gin.Recovery())

	healthHandler := handlers.NewHealthHandler()
	authHandler := handlers.NewAuthHandler(authService)
	projectHandler := handlers.NewProjectHandler(projectService)
	repositoryHandler := handlers.NewRepositoryHandler(repositoryService)
	dashboardHandler := handlers.NewDashboardHandler(postgresDB.DB)
	pipelineHandler := handlers.NewPipelineHandler(
		pipelineRepo,
		runRepo,
		analysisRepo,
		insightRepo,
		postgresDB.DB,
		cfg,
		aiService,
	)

	webhookHandler := handlers.NewWebhookHandler(
		postgresDB.DB,
		pipelineRepo,
		runRepo,
		analysisRepo,
		cfg,
	)

	api := router.Group("/api/v1")
	{
		api.GET("/health", healthHandler.HealthCheck)

		// === Webhook (NO AUTH — GitHub calls this) ===
		api.POST("/webhooks/github", webhookHandler.HandleGitHubWebhook)

		auth := api.Group("/auth")
		{
			auth.POST("/register", authHandler.Register)
			auth.POST("/login", authHandler.Login)
			auth.POST("/refresh", authHandler.Refresh)
		}

		protected := api.Group("")
		protected.Use(middleware.AuthMiddleware(cfg.JWTSecret()))
		{
			// === Dashboard ===
			protected.GET("/dashboard/stats", dashboardHandler.Stats)

			// === User ===
			protected.GET("/me", authHandler.Me)
			protected.PUT("/me", authHandler.UpdateProfile)
			protected.POST("/auth/change-password", authHandler.ChangePassword)

			// === Projects ===
			protected.GET("/projects", projectHandler.List)
			protected.GET("/projects/:projectId", projectHandler.GetByID)
			protected.POST("/projects", projectHandler.Create)
			protected.PUT("/projects/:projectId/compliance", projectHandler.UpdateCompliance)
			protected.DELETE("/projects/:projectId", projectHandler.Delete)

			// === Repositories ===
			protected.POST("/repositories/connect", repositoryHandler.Connect)
			protected.GET("/projects/:projectId/repositories", repositoryHandler.ListByProject)
			protected.GET("/repositories/:repoId", repositoryHandler.GetByID)
			protected.DELETE("/repositories/:repoId", repositoryHandler.Delete)
			protected.GET("/repositories/:repoId/insights", pipelineHandler.GetInsights)
			// Bab 5.13.5: Tahap-1/Tahap-2 detection summary served
			// from the Go-side repository_insights table. Used by
			// the FE as a fallback when the AI service is slow or
			// down so the PDF report cover page still has
			// architecture/technologies/deployment data.
			protected.GET("/repositories/:repoId/pipeline-summary", pipelineHandler.GetPipelineSummary)

			// === Pipelines (Global History) ===
			protected.GET("/pipelines", pipelineHandler.ListAll)
			protected.GET("/pipelines/:pipelineId", pipelineHandler.GetByID)
			protected.DELETE("/pipelines/:pipelineId", pipelineHandler.Delete)
			protected.POST("/pipelines/compare", pipelineHandler.Compare)

			// === Pipelines (Per Repository) ===
			protected.GET("/repositories/:repoId/pipelines", pipelineHandler.ListByRepository)
			protected.GET("/repositories/:repoId/pipelines/:version", pipelineHandler.GetByVersion)
			protected.DELETE("/repositories/:repoId/pipelines/:version", pipelineHandler.DeleteByVersion)
			protected.POST("/repositories/:repoId/pipelines/generate", pipelineHandler.Generate)
			protected.POST("/repositories/:repoId/pipelines/:version/sync-runs", pipelineHandler.SyncRuns)

			// === Repository Analysis ===
			protected.POST("/repositories/:repoId/analyze", pipelineHandler.AnalyzeRepository)

			// === Pipeline Runs ===
			protected.GET("/pipelines/:pipelineId/runs", pipelineHandler.ListRuns)
			protected.GET("/runs/:runId", pipelineHandler.GetRun)
			protected.POST("/runs/:runId/cancel", pipelineHandler.CancelRun)

			// === Pipeline Analysis ===
			protected.GET("/runs/:runId/analysis", pipelineHandler.GetAnalysis)
		}
	}

	router.GET("/health", healthHandler.HealthCheck)

	serverAddr := fmt.Sprintf("%s:%s", cfg.Server.Host, cfg.Server.Port)
	logger.Info("Starting server", zap.String("address", serverAddr))

	if err := router.Run(serverAddr); err != nil {
		logger.Fatal("Failed to start server", zap.Error(err))
	}
}
