package events

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/storage"
	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type OutboxEvent struct {
	ID        int
	EventType string
	Payload   json.RawMessage
}

func StartOutboxRelay() {
	go func() {
		for {
			rows, err := storage.DB.Query("SELECT id, event_type, payload FROM outbox_events WHERE status = 'pending' ORDER BY created_at ASC LIMIT 50")
			if err != nil {
				log.Printf("Outbox relay query error: %v", err)
				time.Sleep(2 * time.Second)
				continue
			}

			var events []OutboxEvent
			for rows.Next() {
				var e OutboxEvent
				if err := rows.Scan(&e.ID, &e.EventType, &e.Payload); err == nil {
					events = append(events, e)
				}
			}
			rows.Close()

			for _, e := range events {
				// Publish to Kafka
				deliveryChan := make(chan kafka.Event)
				err = Producer.Produce(&kafka.Message{
					TopicPartition: kafka.TopicPartition{Topic: &e.EventType, Partition: kafka.PartitionAny},
					Value:          e.Payload,
				}, deliveryChan)

				if err != nil {
					log.Printf("Outbox relay produce error: %v", err)
					continue
				}

				// Wait for ack
				event := <-deliveryChan
				m := event.(*kafka.Message)
				if m.TopicPartition.Error != nil {
					log.Printf("Outbox relay delivery error: %v", m.TopicPartition.Error)
					continue
				}

				// Mark as dispatched
				_, err = storage.DB.Exec("UPDATE outbox_events SET status = 'dispatched' WHERE id = $1", e.ID)
				if err != nil {
					log.Printf("Outbox relay update error: %v", err)
				}
			}

			// If no events were processed, backoff slightly to prevent tight loop
			if len(events) == 0 {
				time.Sleep(1 * time.Second)
			}
		}
	}()
}
