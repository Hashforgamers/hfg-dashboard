BEGIN;

-- Speeds up relation fetch during /api/console/update/vendor/<vendor_id>.
CREATE INDEX IF NOT EXISTS ix_maintenance_status_console_id
    ON maintenance_status (console_id);

COMMIT;
