-- Kiosk auto-extend billed under cafe policy (never recorded as player consent).
-- Apply before deploying hfg-dashboard-service code that reads these columns.
-- Repeatable; existing rows keep NULL basis / opt-in off.
BEGIN;

ALTER TABLE session_extension_policies
  ADD COLUMN IF NOT EXISTS kiosk_auto_extend boolean NOT NULL DEFAULT false;

ALTER TABLE kiosk_runtime_sessions
  ADD COLUMN IF NOT EXISTS credit_basis varchar(24);
ALTER TABLE kiosk_extension_segments
  ADD COLUMN IF NOT EXISTS credit_basis varchar(24);
ALTER TABLE kiosk_session_credit_ledger
  ADD COLUMN IF NOT EXISTS credit_basis varchar(24);

DO $$ BEGIN
  ALTER TABLE kiosk_runtime_sessions ADD CONSTRAINT kiosk_runtime_credit_basis_check
    CHECK (credit_basis IS NULL OR credit_basis IN ('player_consent','cafe_policy'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE kiosk_extension_segments ADD CONSTRAINT kiosk_segment_credit_basis_check
    CHECK (credit_basis IS NULL OR credit_basis IN ('player_consent','cafe_policy','pay_at_desk'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;
