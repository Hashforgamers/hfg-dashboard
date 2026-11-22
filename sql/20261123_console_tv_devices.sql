-- Hash Console Lock (Smart TV) support on the shared kiosk platform.
-- Additive and repeatable: existing PC kiosk links default to PC_KIOSK and
-- keep every current column, token and behaviour. Apply before deploying the
-- hfg-dashboard-service code that pairs TVs; that code checks for
-- device_commands and stays dormant (PC-only) until this has run.
BEGIN;

-- A paired device is still one console_link_sessions row (one revocable
-- bearer credential bound to exactly one cafe station).
ALTER TABLE console_link_sessions
  ADD COLUMN IF NOT EXISTS device_type varchar(16) NOT NULL DEFAULT 'PC_KIOSK',
  ADD COLUMN IF NOT EXISTS device_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- What the TV app says it can do. Never treated as proof.
  ADD COLUMN IF NOT EXISTS reported_capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Per capability: UNVERIFIED / DEVICE_REPORTED_SUCCESS / DEVICE_REPORTED_FAILURE /
  -- UNSUPPORTED / STAFF_CONFIRMED / STAFF_REJECTED, with who and when.
  ADD COLUMN IF NOT EXISTS capability_verification jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS last_heartbeat_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_heartbeat jsonb,
  ADD COLUMN IF NOT EXISTS token_rotated_at timestamptz,
  ADD COLUMN IF NOT EXISTS paired_by varchar(64);

DO $$ BEGIN
  ALTER TABLE console_link_sessions ADD CONSTRAINT console_link_device_type_check
    CHECK (device_type IN ('PC_KIOSK','CONSOLE_TV'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS ix_cls_vendor_device_active
  ON console_link_sessions (vendor_id, device_type) WHERE status = 'active';

-- Station display configuration (console type already lives in consoles.console_type).
ALTER TABLE consoles ADD COLUMN IF NOT EXISTS configured_input_id varchar(32);

-- Short-lived, single-use pairing challenges. The code and the TV's claim
-- secret are stored only as HMACs. vendor/console are set by the approving
-- cafe admin, never by the device.
CREATE TABLE IF NOT EXISTS device_pairing_challenges (
  id uuid PRIMARY KEY,
  device_type varchar(16) NOT NULL CHECK (device_type IN ('CONSOLE_TV')),
  code_hash char(64) NOT NULL,
  claim_secret_hash char(64) NOT NULL,
  device_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  reported_capabilities jsonb NOT NULL DEFAULT '{}'::jsonb,
  status varchar(12) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','approved','claimed','expired','rejected')),
  vendor_id integer,
  console_id integer,
  link_id integer,
  approved_by varchar(64),
  created_ip varchar(64),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at timestamptz NOT NULL,
  approved_at timestamptz,
  claimed_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_device_pairing_open_code
  ON device_pairing_challenges (code_hash) WHERE status IN ('pending','approved');
CREATE INDEX IF NOT EXISTS ix_device_pairing_expiry
  ON device_pairing_challenges (expires_at) WHERE status IN ('pending','approved');

-- Display-control commands sent to a TV. Delivery and the TV's own report are
-- recorded separately: received_at is not success.
CREATE TABLE IF NOT EXISTS device_commands (
  id uuid PRIMARY KEY,
  vendor_id integer NOT NULL,
  console_id integer NOT NULL,
  link_id integer NOT NULL,
  runtime_id varchar(36),
  session_version integer,
  command_type varchar(16) NOT NULL CHECK (command_type IN ('LOCK','UNLOCK','HDMI_TEST')),
  command_status varchar(16) NOT NULL DEFAULT 'PENDING'
    CHECK (command_status IN ('PENDING','SUCCEEDED','FAILED','UNSUPPORTED','UNVERIFIED','SUPERSEDED','EXPIRED')),
  reason varchar(48),
  issued_by varchar(64),
  dedupe_key varchar(160) UNIQUE,
  issued_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at timestamptz NOT NULL,
  received_at timestamptz,
  completed_at timestamptz,
  failure_reason varchar(200),
  result jsonb,
  staff_verification varchar(16) CHECK (staff_verification IN ('CONFIRMED','REJECTED')),
  staff_verified_by varchar(64),
  staff_verified_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_device_commands_link ON device_commands (link_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS ix_device_commands_station ON device_commands (vendor_id, console_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS ix_device_commands_pending ON device_commands (expires_at) WHERE command_status = 'PENDING';

-- Append-only device audit trail (events out, reports in, admin actions).
CREATE TABLE IF NOT EXISTS device_events (
  id bigserial PRIMARY KEY,
  vendor_id integer,
  console_id integer,
  link_id integer,
  runtime_id varchar(36),
  session_version integer,
  direction varchar(8) NOT NULL CHECK (direction IN ('out','in','admin','system')),
  event_type varchar(48) NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  actor varchar(64),
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_device_events_link ON device_events (link_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_device_events_runtime ON device_events (runtime_id, id DESC) WHERE runtime_id IS NOT NULL;

COMMIT;
