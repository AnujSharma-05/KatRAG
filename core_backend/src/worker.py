import json
import logging
import sys
import os
import time
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from minio import Minio

# Local imports
from . import config, models
from .database import SessionLocal

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
            
            # Message payload processing
            try:
                payload = json.loads(msg.value().decode('utf-8'))
                logger.info(f"Received message: {payload}")
                
                document_id = payload.get("document_id")
                organization_id = payload.get("organization_id")
                object_name = payload.get("object_name")
                
                if not document_id or not object_name:
                    logger.error("Missing document_id or object_name in payload")
                    continue
                
                # Database session
                db = SessionLocal()
                try:
                    # Idempotency Check
                    doc = db.query(models.Document).filter(models.Document.id == document_id).first()
                    if not doc:
                        logger.error(f"Document {document_id} not found in DB")
                        continue
                        
                    if doc.status in ["indexed", "processing", "failed"]:
                        logger.warning(f"Document {document_id} is already in state '{doc.status}'. Skipping.")
                        continue
                    
                    # State Update
                    doc.status = "processing"
                    db.commit()
                    logger.info(f"Updated document {document_id} status to processing.")
                    
                    # MinIO Download
                    os.makedirs("/tmp/katrag_processing", exist_ok=True)
                    local_file_path = f"/tmp/katrag_processing/{document_id}.pdf"
                    
                    logger.info(f"Downloading {object_name} from MinIO to {local_file_path}")
                    minio_client.fget_object(config.MINIO_BUCKET_NAME, object_name, local_file_path)
                    
                    # (Pipeline and Status Events will go here)
                    
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down worker...")
    finally:
        consumer.close()
        producer.flush()

if __name__ == "__main__":
    run_worker()
