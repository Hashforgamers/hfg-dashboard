-- Apply before deploying cafe wallet code. Amounts are integer paise.
BEGIN;


CREATE TABLE IF NOT EXISTS cafe_activity_audit (
	id SERIAL NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	actor_id VARCHAR(80) NOT NULL, 
	actor_name VARCHAR(120) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	details JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX IF NOT EXISTS ix_cafe_activity_audit_vendor_id ON cafe_activity_audit (vendor_id);


CREATE TABLE IF NOT EXISTS cafe_food_orders (
	id VARCHAR(36) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	items JSON NOT NULL, 
	amount BIGINT NOT NULL, 
	collector VARCHAR(16) NOT NULL, 
	state VARCHAR(24) NOT NULL, 
	idempotency_key VARCHAR(100) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (vendor_id, user_id, idempotency_key)
)

;

CREATE INDEX IF NOT EXISTS ix_cafe_food_orders_vendor_id ON cafe_food_orders (vendor_id);


CREATE TABLE IF NOT EXISTS cafe_payment_policies (
	vendor_id SERIAL NOT NULL, 
	settings JSON NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (vendor_id)
)

;


CREATE TABLE IF NOT EXISTS cafe_play_sessions (
	id VARCHAR(36) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	console_id INTEGER NOT NULL, 
	link_id INTEGER NOT NULL, 
	console_claim INTEGER, 
	idempotency_key VARCHAR(128) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	state VARCHAR(24) NOT NULL, 
	amount BIGINT NOT NULL, 
	minutes INTEGER NOT NULL, 
	command_token VARCHAR(128) NOT NULL, 
	deadline TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	ends_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (vendor_id, user_id, idempotency_key), 
	UNIQUE (console_claim)
)

;

CREATE INDEX IF NOT EXISTS ix_cafe_play_sessions_vendor_id ON cafe_play_sessions (vendor_id);

CREATE INDEX IF NOT EXISTS ix_cafe_play_ends ON cafe_play_sessions (state, ends_at);

CREATE INDEX IF NOT EXISTS ix_cafe_play_deadline ON cafe_play_sessions (state, deadline);


CREATE TABLE IF NOT EXISTS cafe_staff_sessions (
	jti VARCHAR(64) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	actor_id VARCHAR(80) NOT NULL, 
	actor_name VARCHAR(120) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	closed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (jti)
)

;

CREATE INDEX IF NOT EXISTS ix_cafe_staff_sessions_vendor_id ON cafe_staff_sessions (vendor_id);

CREATE INDEX IF NOT EXISTS ix_cafe_staff_sessions_expires_at ON cafe_staff_sessions (expires_at);


CREATE TABLE IF NOT EXISTS cafe_staff_shifts (
	id VARCHAR(36) NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	actor_id VARCHAR(80) NOT NULL, 
	actor_name VARCHAR(120) NOT NULL, 
	open_key VARCHAR(120), 
	opening_cash BIGINT NOT NULL, 
	counted_cash BIGINT, 
	expected_cash BIGINT, 
	upi_receipts BIGINT, 
	opened_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	closed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (open_key)
)

;

CREATE INDEX IF NOT EXISTS ix_cafe_staff_shifts_vendor_id ON cafe_staff_shifts (vendor_id);


CREATE TABLE IF NOT EXISTS cafe_wallet_ledger (
	id SERIAL NOT NULL, 
	vendor_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	amount BIGINT NOT NULL, 
	balance_after BIGINT NOT NULL, 
	reserved_after BIGINT NOT NULL, 
	actor_id VARCHAR(80) NOT NULL, 
	actor_name VARCHAR(120) NOT NULL, 
	method VARCHAR(32), 
	shift_id VARCHAR(36), 
	session_id VARCHAR(36), 
	reversal_of INTEGER, 
	reason VARCHAR(500) NOT NULL, 
	idempotency_key VARCHAR(128) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (vendor_id, idempotency_key), 
	UNIQUE (reversal_of)
)

;

CREATE INDEX IF NOT EXISTS ix_cafe_wallet_ledger_user_id ON cafe_wallet_ledger (user_id);

CREATE INDEX IF NOT EXISTS ix_cafe_wallet_ledger_vendor_id ON cafe_wallet_ledger (vendor_id);


CREATE TABLE IF NOT EXISTS cafe_wallets (
	vendor_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	balance BIGINT NOT NULL, 
	reserved BIGINT NOT NULL, 
	PRIMARY KEY (vendor_id, user_id), 
	CHECK (balance >= 0 AND reserved >= 0 AND balance >= reserved)
)

;


CREATE OR REPLACE FUNCTION cafe_reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Cafe history is append-only: create a reversal'; END $$;
DROP TRIGGER IF EXISTS cafe_ledger_immutable ON cafe_wallet_ledger;
CREATE TRIGGER cafe_ledger_immutable BEFORE UPDATE OR DELETE ON cafe_wallet_ledger
FOR EACH ROW EXECUTE FUNCTION cafe_reject_history_mutation();
DROP TRIGGER IF EXISTS cafe_audit_immutable ON cafe_activity_audit;
CREATE TRIGGER cafe_audit_immutable BEFORE UPDATE OR DELETE ON cafe_activity_audit
FOR EACH ROW EXECUTE FUNCTION cafe_reject_history_mutation();

-- Legacy availability refreshes must not release a QR session's PC.
CREATE OR REPLACE FUNCTION cafe_guard_availability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM cafe_play_sessions WHERE console_claim = NEW.console_id) THEN
   NEW.is_available := false;
 END IF;
 RETURN NEW;
END $$;

-- Legacy assignments take the same console lock before checking the QR claim.
CREATE OR REPLACE FUNCTION cafe_guard_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.book_status = 'current' AND NEW.console_id IS NOT NULL THEN
   PERFORM id FROM consoles WHERE id = NEW.console_id FOR UPDATE;
   IF EXISTS (SELECT 1 FROM cafe_play_sessions WHERE console_claim = NEW.console_id) THEN
     RAISE EXCEPTION 'Console is reserved by a cafe wallet session';
   END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION cafe_install_console_guards(vid integer) RETURNS void LANGUAGE plpgsql AS $$
DECLARE availability text := 'vendor_' || vid || '_console_availability';
        dashboard text := 'vendor_' || vid || '_dashboard';
BEGIN
 IF to_regclass(availability) IS NULL OR to_regclass(dashboard) IS NULL THEN
   RAISE EXCEPTION 'Cafe console tables are missing';
 END IF;
 EXECUTE format('DROP TRIGGER IF EXISTS cafe_qr_guard ON %I', availability);
 EXECUTE format('CREATE TRIGGER cafe_qr_guard BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION cafe_guard_availability()', availability);
 EXECUTE format('DROP TRIGGER IF EXISTS cafe_qr_guard ON %I', dashboard);
 EXECUTE format('CREATE TRIGGER cafe_qr_guard BEFORE INSERT OR UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION cafe_guard_assignment()', dashboard);
END $$;
COMMIT;
