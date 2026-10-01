BEGIN;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS commercial_terms JSON;
-- Preserve purchased legacy limits/features before the catalog can be edited.
UPDATE subscriptions s SET commercial_terms = json_build_object(
 'package_code',p.code,'package_name',p.name,'pc_limit',p.pc_limit,'extra_pcs',0,
 'billing_cycle',CASE WHEN s.current_period_end-s.current_period_start >= interval '300 days' THEN 'yearly'
                      WHEN s.current_period_end-s.current_period_start >= interval '75 days' THEN 'quarterly' ELSE 'monthly' END,
 'recurring_paise',round(COALESCE(s.unit_amount,0)*100)::bigint,
 'entitlements',COALESCE(p.features::jsonb->'entitlements','["kiosk","pricing","cafe_wallet","passes","food","analytics","tournaments","staff"]'::jsonb),
 'extra_pc_monthly',COALESCE(p.features::jsonb->'extra_pc_monthly','0'::jsonb),
 'cycle_start',s.current_period_start,'cycle_end',s.current_period_end
) FROM packages p WHERE s.package_id=p.id AND (s.commercial_terms IS NULL OR s.commercial_terms::jsonb = 'null'::jsonb);
CREATE TABLE IF NOT EXISTS subscription_checkouts (
 id VARCHAR(36) PRIMARY KEY,
 vendor_id INTEGER NOT NULL REFERENCES vendors(id),
 package_id INTEGER NOT NULL REFERENCES packages(id),
 subscription_id INTEGER REFERENCES subscriptions(id),
 order_id VARCHAR(80) UNIQUE,
 payment_id VARCHAR(80) UNIQUE,
 state VARCHAR(24) NOT NULL DEFAULT 'preview',
 snapshot JSON NOT NULL,
 created_at TIMESTAMPTZ NOT NULL,
 expires_at TIMESTAMPTZ NOT NULL,
 paid_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_subscription_checkouts_vendor_id ON subscription_checkouts(vendor_id);
COMMIT;
