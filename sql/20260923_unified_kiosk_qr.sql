-- Apply after 20260922_cafe_wallet.sql. Existing wallet sessions remain unchanged.
BEGIN;
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS kind varchar(24) NOT NULL DEFAULT 'wallet';
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS booking_ids json NOT NULL DEFAULT '[]';
ALTER TABLE cafe_play_sessions ADD COLUMN IF NOT EXISTS booking_end timestamp;
CREATE TABLE IF NOT EXISTS cafe_booking_claims (
 booking_id integer PRIMARY KEY,
 session_id varchar(36) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cafe_booking_claims_session_id ON cafe_booking_claims(session_id);

-- A reserved booking cannot be started through the legacy route before acknowledgement.
-- A running booking is allowed only on its own PC; other bookings cannot use that PC.
CREATE OR REPLACE FUNCTION cafe_guard_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE bid integer := (to_jsonb(NEW)->>'book_id')::integer;
BEGIN
 IF NEW.book_status = 'current' AND NEW.console_id IS NOT NULL THEN
   PERFORM id FROM consoles WHERE id = NEW.console_id FOR UPDATE;
   IF EXISTS (
       SELECT 1 FROM cafe_play_sessions s WHERE s.console_claim = NEW.console_id
       AND (s.state <> 'active' OR NOT EXISTS (
           SELECT 1 FROM cafe_booking_claims c WHERE c.session_id=s.id AND c.booking_id=bid
       ))
   ) OR EXISTS (
       SELECT 1 FROM cafe_booking_claims c JOIN cafe_play_sessions s ON s.id=c.session_id
       WHERE c.booking_id=bid AND (s.state <> 'active' OR s.console_claim IS DISTINCT FROM NEW.console_id)
   ) THEN
     RAISE EXCEPTION 'Booking or console is already claimed by a QR session';
   END IF;
 END IF;
 RETURN NEW;
END $$;
COMMIT;
