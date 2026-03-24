CREATE TABLE IF NOT EXISTS vendor_notification_preferences (
    vendor_id INTEGER PRIMARY KEY REFERENCES vendors(id) ON DELETE CASCADE,
    app_booking_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    pay_at_cafe_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    hash_wallet_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    payment_gateway_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    pass_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
