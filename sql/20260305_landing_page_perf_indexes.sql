BEGIN;

-- getLandingPage hot path: meals existence lookup by booking_id.
CREATE INDEX IF NOT EXISTS ix_booking_extra_services_booking_id
    ON booking_extra_services (booking_id);

-- Vendor-scoped booking summary joins.
CREATE INDEX IF NOT EXISTS ix_bookings_game_id
    ON bookings (game_id);
CREATE INDEX IF NOT EXISTS ix_slots_gaming_type_id
    ON slots (gaming_type_id);

-- Peak-hour and daily counters on vendor transactions.
CREATE INDEX IF NOT EXISTS ix_transactions_vendor_booking_time
    ON transactions (vendor_id, booking_time);

COMMIT;
