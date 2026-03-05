BEGIN;

-- Speed up join path used by /api/getConsoles/vendor/<vendor_id>.
CREATE INDEX IF NOT EXISTS ix_available_game_console_console_id
    ON available_game_console (console_id);

CREATE INDEX IF NOT EXISTS ix_hardware_specifications_console_id
    ON hardware_specifications (console_id);

COMMIT;
