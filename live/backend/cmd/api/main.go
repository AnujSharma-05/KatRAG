package main

import (
	"log"
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/fiber/v2/middleware/recover"
)

func main() {
	// Initialize the Fiber application
	app := fiber.New(fiber.Config{
		AppName: "CaRAG API Gateway v1",
	})

	// Attach standard middleware
	app.Use(logger.New())  // Logs incoming HTTP requests
	app.Use(recover.New()) // Prevents the server from crashing on panics

	// Health check endpoint
	app.Get("/health", func(c *fiber.Ctx) error {
		return c.JSON(fiber.Map{
			"status":  "healthy",
			"service": "api_gateway",
		})
	})

	// TODO: Attach Proxy Middleware here later

	log.Println("Starting Go API Gateway on port 8080 (changed from 3000 due to milvus-attu collision)...")
	log.Fatal(app.Listen(":8080"))
}

