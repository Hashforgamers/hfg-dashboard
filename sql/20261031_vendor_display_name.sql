-- Apply once to the shared database BEFORE deploying services that read this column.
-- Existing cafes retain cafe_name as their public fallback; legal names are unchanged.
BEGIN;
ALTER TABLE vendors ADD COLUMN IF NOT EXISTS display_name VARCHAR(120);
COMMIT;
