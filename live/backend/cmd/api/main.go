package main

import (
	"log"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/cache"
	"github.com/AnujSharma-05/KatRAG/live/backend/internal/middleware"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
)

func main() {
	// Initialize Redis
	cache.InitRedis("localhost:6379", "", 0)

	// Initialize the Fiber application
	app := fiber.New(fiber.Config{
		AppName: "CaRAG API Gateway v1",
	})

	// Attach standard middleware
	app.Use(logger.New())
	app.Use(recover.New())

	// Health check endpoint (bypasses auth)
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status":  "healthy",
			"service": "api_gateway",
		})
	})

	// All other routes go through the Gateway Proxy
	app.Use(middleware.GatewayProxy())

	log.Println("Starting Go API Gateway on port 8080 (changed from 3000 due to milvus-attu collision)...")
	log.Fatal(app.Listen(":8080"))
}
