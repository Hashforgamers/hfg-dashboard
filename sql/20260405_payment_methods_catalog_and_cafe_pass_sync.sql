-- Heal serial sequences first (handles environments where IDs were inserted manually).
SELECT setval(
  pg_get_serial_sequence('payment_method', 'pay_method_id'),
  COALESCE((SELECT MAX(pay_method_id) FROM payment_method), 0) + 1,
  false
);

SELECT setval(
  pg_get_serial_sequence('payment_vendor_map', 'id'),
  COALESCE((SELECT MAX(id) FROM payment_vendor_map), 0) + 1,
  false
);

-- Canonical payment methods required by dashboard + onboard APIs
INSERT INTO payment_method (method_name, created_at, updated_at)
VALUES
  ('pay_at_cafe', NOW(), NOW()),
  ('hash_global_pass', NOW(), NOW()),
  ('cafe_specific_pass', NOW(), NOW())
ON CONFLICT (method_name) DO NOTHING;

-- Backfill cafe_specific_pass enablement for vendors that already have active cafe passes.
WITH cafe_specific AS (
  SELECT pay_method_id
  FROM payment_method
  WHERE method_name = 'cafe_specific_pass'
  LIMIT 1
), vendor_with_active_pass AS (
  SELECT DISTINCT cp.vendor_id
  FROM cafe_passes cp
  WHERE cp.is_active = TRUE
    AND cp.vendor_id IS NOT NULL
)
INSERT INTO payment_vendor_map (vendor_id, pay_method_id, created_at, updated_at)
SELECT v.vendor_id, c.pay_method_id, NOW(), NOW()
FROM vendor_with_active_pass v
CROSS JOIN cafe_specific c
LEFT JOIN payment_vendor_map pvm
  ON pvm.vendor_id = v.vendor_id
 AND pvm.pay_method_id = c.pay_method_id
WHERE c.pay_method_id IS NOT NULL
  AND pvm.id IS NULL;
