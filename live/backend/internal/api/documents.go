package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"strings"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/auth"
	"github.com/AnujSharma-05/KatRAG/live/backend/internal/events"
	"github.com/AnujSharma-05/KatRAG/live/backend/internal/storage"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
	"github.com/gofiber/fiber/v2"
	"github.com/google/uuid"
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

	scope, err := auth.ResolveScope(c.Context(), userClaims.Subject)
	if err != nil {
		return c.Status(403).JSON(fiber.Map{"error": "Forbidden"})
	}

	hasAccess := false
	for _, g := range scope.GroupIDs {
		if g == groupIDStr {
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

	// 1. Supersession Logic
	var docID int
	var currentVersionNum int
	isSuperseding := false

	err = storage.DB.QueryRow(
		"SELECT id FROM documents WHERE filename = $1 AND group_id = $2 AND organization_id = $3",
		file.Filename, groupID, scope.OrganizationID,
	).Scan(&docID)

	if err == sql.ErrNoRows {
		// New document
		err = storage.DB.QueryRow(
			"INSERT INTO documents (filename, file_size, status, organization_id, group_id, created_at) VALUES ($1, $2, 'pending', $3, $4, CURRENT_TIMESTAMP) RETURNING id",
			file.Filename, file.Size, scope.OrganizationID, groupID,
		).Scan(&docID)
		if err != nil {
			log.Printf("DB insert error: %v", err)
			return c.Status(500).JSON(fiber.Map{"error": "Failed to create document record"})
		}
		currentVersionNum = 1
	} else if err != nil {
		log.Printf("DB select error: %v", err)
		return c.Status(500).JSON(fiber.Map{"error": "Database error"})
	} else {
		// Superseding an existing document
		isSuperseding = true
		err = storage.DB.QueryRow(
			"SELECT COALESCE(MAX(version_num), 0) FROM document_versions WHERE document_id = $1", docID,
		).Scan(&currentVersionNum)
		if err != nil {
			log.Printf("DB max version error: %v", err)
			return c.Status(500).JSON(fiber.Map{"error": "Failed to fetch version info"})
		}

		// Deprecate old versions
		_, err = storage.DB.Exec(
			"UPDATE document_versions SET is_current = false, valid_to = CURRENT_TIMESTAMP WHERE document_id = $1 AND is_current = true", docID,
		)
		if err != nil {
			log.Printf("DB update version error: %v", err)
			return c.Status(500).JSON(fiber.Map{"error": "Failed to deprecate old version"})
		}

		// Update parent doc status
		_, err = storage.DB.Exec(
			"UPDATE documents SET status = 'pending', file_size = $1 WHERE id = $2", file.Size, docID,
		)
		currentVersionNum++
	}

	// Insert new version
	versionID := "ver_" + strings.Replace(uuid.New().String(), "-", "", -1)[:12]
	_, err = storage.DB.Exec(
		"INSERT INTO document_versions (id, document_id, version_num, is_current, valid_from, status) VALUES ($1, $2, $3, true, CURRENT_TIMESTAMP, 'pending')",
		versionID, docID, currentVersionNum,
	)
	if err != nil {
		log.Printf("DB insert version error: %v", err)
		return c.Status(500).JSON(fiber.Map{"error": "Failed to create document version record"})
	}

	// 2. Stream to MinIO
	objectName := fmt.Sprintf("%d_v%d.pdf", docID, currentVersionNum)
	bucketName := "katrag-docs"

	_, err = storage.MinioClient.PutObject(context.Background(), bucketName, objectName, src, file.Size, minio.PutObjectOptions{ContentType: "application/pdf"})
	if err != nil {
		log.Printf("MinIO upload error: %v", err)
		return c.Status(500).JSON(fiber.Map{"error": "Failed to store file"})
	}

	// 3. Publish Events
	topicUpload := "doc.uploaded"
	payloadUpload := map[string]interface{}{
		"document_id":        docID,
		"document_version_id": versionID,
		"group_id":           groupID,
		"organization_id":    scope.OrganizationID,
		"object_name":        objectName,
		"version_num":        currentVersionNum,
	}
	payloadBytes, _ := json.Marshal(payloadUpload)

	err = events.Producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &topicUpload, Partition: kafka.PartitionAny},
		Key:            []byte(scope.OrganizationID),
		Value:          payloadBytes,
	}, nil)

	if isSuperseding {
		topicSuperseded := "doc.superseded"
		payloadSuperseded := map[string]interface{}{
			"document_id":     docID,
			"organization_id": scope.OrganizationID,
			"group_id":        groupID,
			"superseded_by":   versionID,
		}
		supersededBytes, _ := json.Marshal(payloadSuperseded)
		events.Producer.Produce(&kafka.Message{
			TopicPartition: kafka.TopicPartition{Topic: &topicSuperseded, Partition: kafka.PartitionAny},
			Key:            []byte(scope.OrganizationID),
			Value:          supersededBytes,
		}, nil)
	}

	return c.Status(fiber.StatusAccepted).JSON(fiber.Map{
		"message":     "Document upload accepted for processing",
		"document_id": docID,
		"version_id":  versionID,
		"status":      "pending",
	})
}
