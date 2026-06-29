package services

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"net/mail"
	"regexp"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"

	"github.com/user/ai-devsecops-backend/internal/config"
	"github.com/user/ai-devsecops-backend/internal/models"
	"github.com/user/ai-devsecops-backend/internal/repositories"
)

var (
	ErrInvalidEmail       = errors.New("invalid email format")
	ErrWeakPassword       = errors.New("password must be at least 8 characters")
	ErrInvalidRole        = errors.New("invalid role")
	ErrInvalidCredentials = errors.New("invalid email or password")
	ErrInvalidToken       = errors.New("invalid or expired refresh token")
)

type AuthService struct {
	userRepo         repositories.UserRepository
	refreshTokenRepo repositories.RefreshTokenRepository
	cfg              *config.Config
}

func NewAuthService(
	userRepo repositories.UserRepository,
	refreshTokenRepo repositories.RefreshTokenRepository,
	cfg *config.Config,
) *AuthService {
	return &AuthService{
		userRepo:         userRepo,
		refreshTokenRepo: refreshTokenRepo,
		cfg:              cfg,
	}
}

func (s *AuthService) Register(email, password, name string) (*models.User, error) {
	if _, err := mail.ParseAddress(email); err != nil {
		return nil, ErrInvalidEmail
	}

	if len(password) < 8 {
		return nil, ErrWeakPassword
	}

	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}

	user := &models.User{
		ID:           uuid.New(),
		Email:        email,
		PasswordHash: string(hashedPassword),
		Name:         name,
		Role:         models.RoleEngineer,
	}

	if err := s.userRepo.Create(user); err != nil {
		re := regexp.MustCompile(`(?i)duplicate|unique`)
		if re.MatchString(err.Error()) {
			return nil, errors.New("email already registered")
		}
		return nil, err
	}

	return user, nil
}

func (s *AuthService) Login(email, password string) (accessToken string, refreshToken string, err error) {
	user, err := s.userRepo.FindByEmail(email)
	if err != nil {
		return "", "", ErrInvalidCredentials
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)); err != nil {
		return "", "", ErrInvalidCredentials
	}

	accessToken, err = s.generateAccessToken(user.ID, user.Role)
	if err != nil {
		return "", "", err
	}

	refreshToken, err = s.generateRefreshToken(user.ID)
	if err != nil {
		return "", "", err
	}

	return accessToken, refreshToken, nil
}

func (s *AuthService) RefreshToken(refreshTokenStr string) (newAccessToken string, newRefreshToken string, err error) {
	hashedToken := hashToken(refreshTokenStr)
	stored, err := s.refreshTokenRepo.FindByToken(hashedToken)
	if err != nil {
		return "", "", ErrInvalidToken
	}

	if time.Now().After(stored.ExpiresAt) {
		s.refreshTokenRepo.Delete(stored.ID)
		return "", "", ErrInvalidToken
	}

	_ = s.refreshTokenRepo.Delete(stored.ID)

	user, err := s.userRepo.FindByID(stored.UserID)
	if err != nil {
		return "", "", ErrInvalidToken
	}

	newAccessToken, err = s.generateAccessToken(user.ID, user.Role)
	if err != nil {
		return "", "", err
	}

	newRefreshToken, err = s.generateRefreshToken(user.ID)
	if err != nil {
		return "", "", err
	}

	return newAccessToken, newRefreshToken, nil
}

func (s *AuthService) generateAccessToken(userID uuid.UUID, role string) (string, error) {
	claims := jwt.MapClaims{
		"sub":  userID.String(),
		"role": role,
		"exp":  time.Now().Add(s.cfg.AccessTokenDuration()).Unix(),
		"iat":  time.Now().Unix(),
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(s.cfg.JWTSecret()))
}

func (s *AuthService) generateRefreshToken(userID uuid.UUID) (string, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", err
	}
	tokenStr := hex.EncodeToString(raw)

	hashed := hashToken(tokenStr)

	rt := &models.RefreshToken{
		ID:        uuid.New(),
		UserID:    userID,
		Token:     hashed,
		ExpiresAt: time.Now().Add(s.cfg.RefreshTokenDuration()),
	}

	if err := s.refreshTokenRepo.Create(rt); err != nil {
		return "", err
	}

	return tokenStr, nil
}

func hashToken(token string) string {
	h := sha256.New()
	h.Write([]byte(token))
	return hex.EncodeToString(h.Sum(nil))
}

func (s *AuthService) GetUserByID(userID uuid.UUID) (*models.User, error) {
	return s.userRepo.FindByID(userID)
}

func (s *AuthService) UpdateUser(userID uuid.UUID, displayName, email string) (*models.User, error) {
	user, err := s.userRepo.FindByID(userID)
	if err != nil {
		return nil, err
	}
	if displayName != "" {
		user.Name = displayName
	}
	if email != "" {
		if _, err := mail.ParseAddress(email); err != nil {
			return nil, ErrInvalidEmail
		}
		user.Email = email
	}
	if err := s.userRepo.Update(user); err != nil {
		return nil, err
	}
	return user, nil
}

func (s *AuthService) ChangePassword(userID uuid.UUID, currentPassword, newPassword string) error {
	user, err := s.userRepo.FindByID(userID)
	if err != nil {
		return err
	}
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(currentPassword)); err != nil {
		return ErrInvalidCredentials
	}
	if len(newPassword) < 8 {
		return ErrWeakPassword
	}
	hashed, err := bcrypt.GenerateFromPassword([]byte(newPassword), bcrypt.DefaultCost)
	if err != nil {
		return err
	}
	user.PasswordHash = string(hashed)
	return s.userRepo.Update(user)
}
