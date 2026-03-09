BEGIN;

-- Speed up /vendor/<vendor_id>/vendor-games hot path.
CREATE INDEX IF NOT EXISTS ix_vendor_games_vendor_available
    ON vendor_games (vendor_id, is_available, game_id, console_id);

-- Fast console -> available_game resolution.
CREATE INDEX IF NOT EXISTS ix_available_game_console_console_game
    ON available_game_console (console_id, available_game_id);

-- Fast active-offer filtering for vendor/game with date window checks.
CREATE INDEX IF NOT EXISTS ix_console_pricing_offers_vendor_game_active_window
    ON console_pricing_offers (vendor_id, available_game_id, is_active, start_date, end_date, id);

COMMIT;
