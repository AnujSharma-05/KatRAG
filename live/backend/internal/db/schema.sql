CREATE TABLE IF NOT EXISTS outbox_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE document_versions 
ADD CONSTRAINT no_overlapping_versions 
EXCLUDE USING gist (
    document_id WITH =, 
    tstzrange(valid_from, COALESCE(valid_to, 'infinity'), '[)') WITH &&
);
