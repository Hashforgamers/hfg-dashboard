BEGIN;
-- Record the one-time compatibility seed so reruns preserve later cafe choices.
CREATE TABLE IF NOT EXISTS payment_method_migrations (
    name varchar(100) PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
);
LOCK TABLE payment_method_migrations IN EXCLUSIVE MODE;
DO $migration$
BEGIN
IF NOT EXISTS (SELECT 1 FROM payment_method_migrations WHERE name='six_methods_v1') THEN
INSERT INTO payment_method(method_name) VALUES
 ('hash_wallet'),('cafe_wallet'),('hash_global_pass'),('cafe_specific_pass'),('payment_gateway'),('pay_at_cafe')
ON CONFLICT(method_name) DO NOTHING;
-- Preserve legacy online/wallet acceptance on upgrade. Subsequent changes are explicit.
INSERT INTO payment_vendor_map(vendor_id,pay_method_id)
SELECT v.id, pm.pay_method_id FROM vendors v CROSS JOIN payment_method pm
WHERE pm.method_name IN ('hash_wallet','payment_gateway')
ON CONFLICT(vendor_id,pay_method_id) DO NOTHING;
INSERT INTO payment_vendor_map(vendor_id,pay_method_id)
SELECT cp.vendor_id,pm.pay_method_id FROM cafe_payment_policies cp CROSS JOIN payment_method pm
WHERE pm.method_name='cafe_wallet'
ON CONFLICT(vendor_id,pay_method_id) DO NOTHING;
-- Existing cafe passes were auto-accepted before this release; preserve on first upgrade.
INSERT INTO payment_vendor_map(vendor_id,pay_method_id)
SELECT DISTINCT cp.vendor_id,pm.pay_method_id FROM cafe_passes cp CROSS JOIN payment_method pm
WHERE cp.vendor_id IS NOT NULL AND cp.is_active AND pm.method_name='cafe_specific_pass'
ON CONFLICT(vendor_id,pay_method_id) DO NOTHING;
INSERT INTO payment_method_migrations(name) VALUES ('six_methods_v1');
END IF;
END $migration$;
COMMIT;
