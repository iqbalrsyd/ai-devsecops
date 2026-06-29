package database

import (
	"context"
	"fmt"
	"log"

	"github.com/go-redis/redis/v8"
	"github.com/user/ai-devsecops-backend/internal/config"
)

type RedisDB struct {
	*redis.Client
}

func NewRedisConnection(cfg *config.Config) (*RedisDB, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", cfg.Redis.Host, cfg.Redis.Port),
		Password: cfg.Redis.Password,
		DB:       cfg.Redis.DB,
	})

	// Test connection
	ctx := context.Background()
	_, err := rdb.Ping(ctx).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to redis: %w", err)
	}

	log.Println("Successfully connected to Redis")

	return &RedisDB{Client: rdb}, nil
}

func (rdb *RedisDB) Close() error {
	return rdb.Client.Close()
}
