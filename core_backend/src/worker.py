import json
import logging
import sys
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from minio import Minio

# Local imports
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def initialize_minio():
    client = Minio(
        config.MINIO_ENDPOINT,
        access_key=config.MINIO_ACCESS_KEY,
        secret_key=config.MINIO_SECRET_KEY,
        secure=False  # Local Docker setup
    )
    # Ensure bucket exists
    found = client.bucket_exists(config.MINIO_BUCKET_NAME)
    if not found:
        client.make_bucket(config.MINIO_BUCKET_NAME)
        logger.info(f"Created MinIO bucket: {config.MINIO_BUCKET_NAME}")
    return client

def run_worker():
    # 1. Initialize MinIO
    minio_client = initialize_minio()

    # 2. Initialize Kafka Consumer
    consumer_conf = {
        'bootstrap.servers': config.KAFKA_BROKER_URL,
        'group.id': 'katrag-ingestion-group',
        'auto.offset.reset': 'earliest'
    }
    consumer = Consumer(consumer_conf)
    
    # 3. Initialize Kafka Producer
    producer_conf = {
        'bootstrap.servers': config.KAFKA_BROKER_URL
    }
    producer = Producer(producer_conf)

    topic_in = "doc.uploaded"
    consumer.subscribe([topic_in])

    logger.info(f"Worker started. Subscribed to topic: {topic_in}")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    raise KafkaException(msg.error())
            
            # Message payload processing will be implemented here
            try:
                payload = json.loads(msg.value().decode('utf-8'))
                logger.info(f"Received message: {payload}")
                
                # TODO: Implement idempotency, MinIO download, and processing pipeline
                
                # Acknowledge the message (if manual commit is enabled, but default auto commit works for now)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down worker...")
    finally:
        consumer.close()
        producer.flush()

if __name__ == "__main__":
    run_worker()
