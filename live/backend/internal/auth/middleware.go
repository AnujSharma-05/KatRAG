package auth

import (
	"github.com/gofiber/fiber/v2"
)

type Claims struct {
	Subject string
}

func JWTMiddleware(c *fiber.Ctx) error {
	authHeader := c.Get("Authorization")
	if authHeader == "" {
		token := c.Query("token")
		if token != "" {
			authHeader = "Bearer " + token
		}
	}
	
	sub, err := ParseJWT(authHeader)
	if err != nil {
		return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{"error": err.Error()})
	}
	c.Locals("user", &Claims{Subject: sub})
	return c.Next()
}
