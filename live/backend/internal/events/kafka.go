package events

import (
	"log"

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
