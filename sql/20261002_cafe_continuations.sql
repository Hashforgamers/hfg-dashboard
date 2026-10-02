-- Apply AFTER 20261002_shared_slot_reservations.sql, before deploying runtime.
BEGIN;
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS warning_sent_at timestamp;
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS due_amount bigint NOT NULL DEFAULT 0 CHECK (due_amount>=0);
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS settled_at timestamp;
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS ended_at timestamp;
CREATE TABLE IF NOT EXISTS cafe_continuations (
    id varchar(36) PRIMARY KEY, vendor_id integer NOT NULL, user_id integer NOT NULL,
    parent_id varchar(36) NOT NULL REFERENCES cafe_play_sessions(id),
    session_id varchar(36) UNIQUE REFERENCES cafe_play_sessions(id),
    pending_key varchar(36) UNIQUE, idempotency_key varchar(100) NOT NULL,
    fingerprint varchar(64) NOT NULL, minutes integer NOT NULL CHECK(minutes BETWEEN 5 AND 720),
    amount bigint NOT NULL CHECK(amount>=0), state varchar(24) NOT NULL DEFAULT 'pending',
    expires_at timestamp NOT NULL, decided_at timestamp, decided_by varchar(80),
    created_at timestamp NOT NULL DEFAULT now(), UNIQUE(vendor_id,user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_cafe_continuations_vendor_id ON cafe_continuations(vendor_id);
CREATE TABLE IF NOT EXISTS cafe_owner_email_outbox (
    request_id varchar(36) PRIMARY KEY REFERENCES cafe_continuations(id),
    recipient varchar(255), attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamp NOT NULL DEFAULT now(), sent_at timestamp, last_error varchar(255)
);
COMMIT;
