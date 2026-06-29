package config

import "time"

func (c *Config) JWTSecret() string {
	return c.JWT.Secret
}

func (c *Config) AccessTokenDuration() time.Duration {
	d, err := time.ParseDuration(c.JWT.AccessDuration)
	if err != nil {
		return 15 * time.Minute
	}
	return d
}

func (c *Config) RefreshTokenDuration() time.Duration {
	d, err := time.ParseDuration(c.JWT.RefreshDuration)
	if err != nil {
		return 7 * 24 * time.Hour
	}
	return d
}
