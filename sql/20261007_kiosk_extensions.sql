-- Apply to shared PostgreSQL before new kiosk clients.

BEGIN;


CREATE TABLE IF NOT EXISTS kiosk_runtime_mutations (
	runtime_id VARCHAR(36) NOT NULL, 
	idempotency_key VARCHAR(100) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	PRIMARY KEY (runtime_id, idempotency_key)
)

;


CREATE TABLE IF NOT EXISTS kiosk_runtime_sessions (
	id VARCHAR(36) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	console_id INTEGER NOT NULL, 
	link_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	console_claim INTEGER, 
	source_kind VARCHAR(16) NOT NULL, 
	source_id VARCHAR(36) NOT NULL, 
	booking_ids JSON NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	paid_until TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reserved_until TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	billed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ended_at TIMESTAMP WITHOUT TIME ZONE, 
	stop_at TIMESTAMP WITHOUT TIME ZONE, 
	rolling BOOLEAN NOT NULL, 
	credit_consent BOOLEAN NOT NULL, 
	credit_mode VARCHAR(24) NOT NULL, 
	credit_limit BIGINT, 
	revision INTEGER NOT NULL, 
	event_sequence INTEGER NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	reason VARCHAR(80), 
	notice_boundary TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (source_kind, source_id, console_id), 
	UNIQUE (console_claim)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_runtime_sessions_vendor_id ON kiosk_runtime_sessions (vendor_id);


CREATE TABLE IF NOT EXISTS session_extension_policies (
	vendor_id SERIAL NOT NULL, 
	credit_mode VARCHAR(24) NOT NULL, 
	credit_limit BIGINT, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (vendor_id)
)

;


CREATE TABLE IF NOT EXISTS kiosk_base_slot_releases (
	booking_id INTEGER NOT NULL, 
	console_id INTEGER NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	units INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (booking_id, console_id), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id)
)

;


CREATE TABLE IF NOT EXISTS kiosk_extension_quotes (
	id VARCHAR(36) NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	revision INTEGER NOT NULL, 
	starts_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ends_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	amount BIGINT NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	pricing_basis JSON, 
	idempotency_key VARCHAR(100), 
	fingerprint VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id), 
	UNIQUE (idempotency_key)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_extension_quotes_runtime_id ON kiosk_extension_quotes (runtime_id);


CREATE TABLE IF NOT EXISTS kiosk_extension_segments (
	id VARCHAR(36) NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	starts_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	ends_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	amount BIGINT NOT NULL, 
	funding BIGINT NOT NULL, 
	captured BIGINT NOT NULL, 
	charged BIGINT NOT NULL, 
	credit_due BIGINT NOT NULL, 
	credit_paid BIGINT NOT NULL, 
	closed BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (runtime_id, starts_at), 
	CHECK (amount >= 0 AND funding >= 0 AND funding <= amount AND captured >= 0 AND captured <= funding AND charged >= 0 AND charged <= amount AND credit_due >= 0 AND credit_paid >= 0 AND credit_paid <= credit_due), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_extension_segments_runtime_id ON kiosk_extension_segments (runtime_id);


CREATE TABLE IF NOT EXISTS kiosk_session_notices (
	id VARCHAR(36) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	details JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	read_at TIMESTAMP WITHOUT TIME ZONE, 
	dedupe_key VARCHAR(150), 
	PRIMARY KEY (id), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id), 
	UNIQUE (dedupe_key)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_session_notices_vendor_id ON kiosk_session_notices (vendor_id);


CREATE TABLE IF NOT EXISTS kiosk_session_outbox (
	id VARCHAR(36) NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	revision INTEGER NOT NULL, 
	snapshot JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	published_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_outbox_pending ON kiosk_session_outbox (published_at, created_at);


CREATE TABLE IF NOT EXISTS kiosk_session_receipts (
	id VARCHAR(36) NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	amount BIGINT NOT NULL, 
	method VARCHAR(24) NOT NULL, 
	actor_id VARCHAR(80) NOT NULL, 
	idempotency_key VARCHAR(100) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (vendor_id, idempotency_key), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_session_receipts_runtime_id ON kiosk_session_receipts (runtime_id);


CREATE TABLE IF NOT EXISTS kiosk_session_credit_ledger (
	id VARCHAR(36) NOT NULL, 
	runtime_id VARCHAR(36) NOT NULL, 
	segment_id VARCHAR(36) NOT NULL, 
	amount BIGINT NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	idempotency_key VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(runtime_id) REFERENCES kiosk_runtime_sessions (id), 
	FOREIGN KEY(segment_id) REFERENCES kiosk_extension_segments (id), 
	UNIQUE (idempotency_key)
)

;

CREATE INDEX IF NOT EXISTS ix_kiosk_session_credit_ledger_runtime_id ON kiosk_session_credit_ledger (runtime_id);

CREATE OR REPLACE FUNCTION cafe_guard_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE bid integer := (to_jsonb(NEW)->>'book_id')::integer;
        starts timestamp;
        finishes timestamp;
        conflict boolean;
BEGIN
 IF NEW.book_status IN ('current','upcoming') AND NEW.console_id > 0 THEN
   PERFORM id FROM consoles WHERE id=NEW.console_id OR id IN (
       SELECT jsonb_array_elements_text(COALESCE(b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb))::integer
       FROM bookings b WHERE b.id=bid) ORDER BY id FOR UPDATE;
   starts := NEW.date + NEW.start_time;
   finishes := NEW.date + NEW.end_time;
   IF finishes <= starts THEN finishes := finishes + interval '1 day'; END IF;
   EXECUTE format('SELECT EXISTS (SELECT 1 FROM %I d LEFT JOIN bookings guard_b ON guard_b.id=d.book_id WHERE (d.console_id=$1 OR
       (COALESCE(guard_b.squad_details::jsonb->''assigned_console_ids'',''[]''::jsonb) @> to_jsonb($1)
        AND NOT COALESCE(guard_b.squad_details::jsonb->''released_console_ids'',''[]''::jsonb) @> to_jsonb($1)))
       AND d.book_status IN (''current'',''upcoming'') AND d.book_id IS DISTINCT FROM $2
       AND (($3=''current'' AND d.book_status=''current'' AND NOT EXISTS (
            SELECT 1 FROM bookings old_b JOIN bookings new_b ON new_b.id=$2
            WHERE old_b.id=d.book_id AND old_b.user_id=new_b.user_id
              AND old_b.game_id=new_b.game_id AND old_b.access_code_id IS NOT NULL
              AND old_b.access_code_id=new_b.access_code_id)) OR
          (d.date+d.start_time < $5 AND $4 < d.date+d.end_time+
              CASE WHEN d.end_time<=d.start_time THEN interval ''1 day'' ELSE interval ''0 day'' END)))',TG_TABLE_NAME)
       INTO conflict USING NEW.console_id,bid,NEW.book_status,starts,finishes;
   IF conflict THEN
     RAISE EXCEPTION 'Console already has a booking during this interval' USING ERRCODE='23514';
   END IF;
   IF EXISTS (SELECT 1 FROM kiosk_runtime_sessions r WHERE (r.console_id=NEW.console_id OR EXISTS (SELECT 1 FROM bookings owner_b WHERE owner_b.id=bid
           AND COALESCE(owner_b.squad_details::jsonb->'assigned_console_ids','[]'::jsonb) @> to_jsonb(r.console_id)
           AND NOT COALESCE(owner_b.squad_details::jsonb->'released_console_ids','[]'::jsonb) @> to_jsonb(r.console_id)))
       AND r.ended_at IS NULL AND NOT (r.source_kind='booking' AND r.booking_ids::jsonb @> to_jsonb(bid))
       AND starts < ((r.reserved_until AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata')
       AND ((r.started_at AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata') < finishes) THEN
     RAISE EXCEPTION 'Console interval held by session extension' USING ERRCODE='23514';
   END IF;
   IF EXISTS (
     SELECT 1 FROM cafe_play_sessions s WHERE s.console_claim=NEW.console_id
       AND NOT EXISTS (SELECT 1 FROM cafe_booking_claims c WHERE c.session_id=s.id AND c.booking_id=bid)
       AND (NEW.book_status='current' OR
         (starts < ((COALESCE(s.ends_at,s.booking_end,s.deadline + s.minutes * interval '1 minute') AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata')
           AND ((COALESCE(s.started_at,s.created_at) AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata') < finishes))
   ) OR (NEW.book_status='current' AND EXISTS (
     SELECT 1 FROM cafe_booking_claims c JOIN cafe_play_sessions s ON s.id=c.session_id
     WHERE c.booking_id=bid AND (s.state <> 'active' OR s.console_claim IS DISTINCT FROM NEW.console_id)
   )) THEN
     RAISE EXCEPTION 'Booking or console is already claimed by a QR session' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END $$;













COMMIT;