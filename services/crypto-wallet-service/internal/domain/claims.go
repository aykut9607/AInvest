package domain

import "github.com/golang-jwt/jwt/v5"

type MyClaims struct {
	UserID string `json:"user_id"`
	jwt.RegisteredClaims
}