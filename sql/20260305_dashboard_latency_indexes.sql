BEGIN;

-- Transaction report and dashboard counters
CREATE INDEX IF NOT EXISTS ix_transactions_vendor_booking_date_time
    ON transactions (vendor_id, booking_date DESC, booking_time DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_transactions_vendor_settlement_status
    ON transactions (vendor_id, settlement_status);
CREATE INDEX IF NOT EXISTS ix_transactions_vendor_booked_date
    ON transactions (vendor_id, booked_date);

-- Pricing lookups
CREATE INDEX IF NOT EXISTS ix_console_pricing_offers_vendor_game_window
    ON console_pricing_offers (vendor_id, available_game_id, is_active, start_date, end_date);

-- Vendor-scoped lookups
CREATE INDEX IF NOT EXISTS ix_available_games_vendor_id
    ON available_games (vendor_id);
CREATE INDEX IF NOT EXISTS ix_controller_pricing_rules_vendor_game
    ON controller_pricing_rules (vendor_id, available_game_id);

COMMIT;
