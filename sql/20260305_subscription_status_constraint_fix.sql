BEGIN;

-- Old constraint is too strict: it allows only one row per status per vendor,
-- which blocks normal history creation (multiple expired/canceled rows).
ALTER TABLE subscriptions
    DROP CONSTRAINT IF EXISTS uq_vendor_status;

-- Keep data rule we actually need:
-- max one OPEN subscription per vendor (active/trialing/past_due).
DROP INDEX IF EXISTS uq_subscription_open_vendor;
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_open_vendor
    ON subscriptions (vendor_id)
    WHERE status IN ('active', 'trialing', 'past_due');

COMMIT;

