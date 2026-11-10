BEGIN;
ALTER TABLE hardware_specifications ADD COLUMN IF NOT EXISTS screen_size_inches integer;
ALTER TABLE hardware_specifications DROP CONSTRAINT IF EXISTS hardware_screen_size_range;
ALTER TABLE hardware_specifications ADD CONSTRAINT hardware_screen_size_range
    CHECK (screen_size_inches BETWEEN 1 AND 1000);
COMMIT;
