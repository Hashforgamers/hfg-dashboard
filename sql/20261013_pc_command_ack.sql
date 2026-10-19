BEGIN;
CREATE TABLE IF NOT EXISTS pc_session_commands (
 id UUID PRIMARY KEY, vendor_id INTEGER NOT NULL, console_id INTEGER NOT NULL,
 booking_id INTEGER NOT NULL, action VARCHAR(12) NOT NULL CHECK(action IN ('unlock','lock')),
 state VARCHAR(12) NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','acked','failed')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, acknowledged_at TIMESTAMPTZ,
 UNIQUE(vendor_id,console_id,booking_id,action)
);
DO $$ BEGIN
 IF to_regclass('kiosk_extension_segments') IS NOT NULL THEN
  ALTER TABLE kiosk_extension_segments ADD COLUMN IF NOT EXISTS is_overrun BOOLEAN NOT NULL DEFAULT FALSE;
 END IF;
END $$;
COMMIT;
