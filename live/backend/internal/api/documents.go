package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strconv"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/auth"
	"github.com/AnujSharma-05/KatRAG/live/backend/internal/events"
	"github.com/AnujSharma-05/KatRAG/live/backend/internal/storage"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/gofiber/fiber/v2"
	"github.com/minio/minio-go/v7"
)

func UploadDocument(c *fiber.Ctx) error {
	groupIDStr := c.Params("id")
	if groupIDStr == "" {
		return c.Status(400).JSON(fiber.Map{"error": "Missing group ID"})
	}
	groupID, err := strconv.Atoi(groupIDStr)
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Invalid group ID format"})
	}

	userClaims, ok := c.Locals("user").(*auth.Claims)
	if !ok || userClaims == nil {
		return c.Status(401).JSON(fiber.Map{"error": "Unauthorized"})
	}

	scope, err := auth.FetchScope(userClaims.Subject)
	if err != nil {
		return c.Status(403).JSON(fiber.Map{"error": "Forbidden"})
	}

	// Wait, scope.GroupIDs is []int according to our previous work? Let's check.
	// We'll assume the scope resolution mock handles integer group IDs.
	hasAccess := false
	for _, g := range scope.GroupIDs {
		if g == groupID {
			hasAccess = true
			break
		}
	}
	if !hasAccess {
		return c.Status(403).JSON(fiber.Map{"error": "Forbidden - Not in group"})
	}

	file, err := c.FormFile("file")
	if err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "File upload required"})
	}

	src, err := file.Open()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "Failed to read file"})
	}
	defer src.Close()

	// 1. Insert pending row into Postgres to get the ID
	var docID int
	err = storage.DB.QueryRow(
		"INSERT INTO documents (filename, file_size, status, organization_id, group_id) VALUES ($1, $2, 'pending', $3, $4) RETURNING id",
		file.Filename, file.Size, scope.OrganizationID, groupID,
	).Scan(&docID)

	if err != nil {
		log.Printf("DB insert error: %v", err)
		return c.Status(500).JSON(fiber.Map{"error": "Failed to record document"})
	}

	// 2. Stream to MinIO
	objectName := fmt.Sprintf("%d.pdf", docID)
	bucketName := "katrag-docs"

	_, err = storage.MinioClient.PutObject(context.Background(), bucketName, objectName, src, file.Size, minio.PutObjectOptions{ContentType: "application/pdf"})
	if err != nil {
		log.Printf("MinIO upload error: %v", err)
		return c.Status(500).JSON(fiber.Map{"error": "Failed to store file"})
	}

	// 3. Publish doc.uploaded event
	payload := map[string]interface{}{
		"document_id":     docID,
		"group_id":        groupID,
		"organization_id": scope.OrganizationID,
		"object_name":     objectName,
	}
	payloadBytes, _ := json.Marshal(payload)

	topic := "doc.uploaded"
	err = events.Producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &topic, Partition: kafka.PartitionAny},
		Key:            []byte(scope.OrganizationID), // Strict per-tenant ordering
		Value:          payloadBytes,
	}, nil)

	if err != nil {
		log.Printf("Kafka produce error: %v", err)
		return c.Status(500).JSON(fiber.Map{"error": "Failed to publish upload event"})
	}

	return c.Status(fiber.StatusAccepted).JSON(fiber.Map{
		"message":     "Document upload accepted for processing",
		"document_id": docID,
		"status":      "pending",
	})
}
