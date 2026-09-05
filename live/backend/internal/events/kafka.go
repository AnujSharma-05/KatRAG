package events

import (
	"encoding/json"
	"log"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/ws"
	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

var Producer *kafka.Producer

func InitKafkaProducer(brokerURL string) {
	p, err := kafka.NewProducer(&kafka.ConfigMap{"bootstrap.servers": brokerURL})
	if err != nil {
		log.Fatalf("Failed to create Kafka producer: %s\n", err)
	}
	Producer = p
	log.Println("Kafka producer initialized")
}

func StartKafkaConsumer(brokerURL string) {
	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers": brokerURL,
		"group.id":          "katrag-gateway-broadcaster",
		"auto.offset.reset": "earliest",
	})

	if err != nil {
		log.Fatalf("Failed to create Kafka consumer: %s\n", err)
	}

	err = c.SubscribeTopics([]string{"doc.indexed", "doc.failed"}, nil)
	if err != nil {
		log.Fatalf("Failed to subscribe to topics: %s\n", err)
	}

	log.Println("Kafka consumer started listening for status events...")

	go func() {
		for {
			msg, err := c.ReadMessage(-1)
			if err == nil {
				log.Printf("Received Kafka event on %s: %s\n", *msg.TopicPartition.Topic, string(msg.Value))
				
				var payload map[string]interface{}
				if err := json.Unmarshal(msg.Value, &payload); err == nil {
					// Extract group_id and broadcast
					if groupIDFloat, ok := payload["group_id"].(float64); ok {
						groupID := int(groupIDFloat)
						ws.GlobalBroadcaster.Broadcast(groupID, msg.Value)
					}
				}
			} else {
				log.Printf("Kafka consumer error: %v (%v)\n", err, msg)
			}
		}
	}()
}
