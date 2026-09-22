BEGIN;
-- Durable across workers/restarts. Keep redemptions for the lifetime of the code.
CREATE TABLE IF NOT EXISTS kiosk_code_redemptions (
    access_code_id INTEGER PRIMARY KEY REFERENCES access_booking_codes(id) ON DELETE CASCADE,
    console_id INTEGER NOT NULL REFERENCES consoles(id),
    booking_id INTEGER NOT NULL REFERENCES bookings(id),
    redeemed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kiosk_idempotency (
    principal TEXT NOT NULL,
    key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    response JSONB NOT NULL,
    status_code INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (principal, key)
);
CREATE TABLE IF NOT EXISTS kiosk_rate_limits (
    key TEXT PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    attempts INTEGER NOT NULL
);
COMMIT;
