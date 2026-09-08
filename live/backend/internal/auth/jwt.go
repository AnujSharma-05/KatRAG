package auth

import (
	"errors"
	"fmt"
	"os"
	"strings"

	"github.com/golang-jwt/jwt/v5"
)

func getJWTSecret() []byte {
	secret := os.Getenv("KATRAG_JWT_SECRET")
	if secret == "" {
		panic("KATRAG_JWT_SECRET environment variable is not set")
	}
	return []byte(secret)
}

// ParseJWT validates a Bearer token and returns the UserID
func ParseJWT(authHeader string) (string, error) {
	if authHeader == "" {
		return "", errors.New("missing authorization header")
	}

	parts := strings.Split(authHeader, " ")
	if len(parts) != 2 || parts[0] != "Bearer" {
		return "", errors.New("invalid authorization format")
	}
	tokenString := parts[1]

	token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
		// Validate the alg
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return getJWTSecret(), nil
	})

	if err != nil {
		return "", err
	}

	if claims, ok := token.Claims.(jwt.MapClaims); ok && token.Valid {
		// Extract "sub" claim as user ID
		if sub, ok := claims["sub"].(string); ok {
			return sub, nil
		}
		return "", errors.New("missing 'sub' claim in token")
	}

	return "", errors.New("invalid token")
}

