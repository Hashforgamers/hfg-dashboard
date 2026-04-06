-- Enable "Pay at Cafe" for all existing vendors.
-- Safe to run multiple times.

-- 1) Heal sequences (protects against prior manual inserts)
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

-- 2) Ensure canonical pay_at_cafe method exists
INSERT INTO payment_method (method_name, created_at, updated_at)
VALUES ('pay_at_cafe', NOW(), NOW())
ON CONFLICT (method_name) DO NOTHING;

-- 3) Resolve pay_at_cafe method id (supports legacy naming already present)
WITH pay_at_cafe_method AS (
  SELECT pm.pay_method_id
  FROM payment_method pm
  WHERE lower(replace(replace(pm.method_name, '_', ' '), '-', ' ')) IN (
    'pay at cafe',
    'pay in cafe'
  )
  ORDER BY CASE WHEN pm.method_name = 'pay_at_cafe' THEN 0 ELSE 1 END, pm.pay_method_id
  LIMIT 1
)
INSERT INTO payment_vendor_map (vendor_id, pay_method_id, created_at, updated_at)
SELECT v.id, pcm.pay_method_id, NOW(), NOW()
FROM vendors v
CROSS JOIN pay_at_cafe_method pcm
LEFT JOIN payment_vendor_map pvm
  ON pvm.vendor_id = v.id
 AND pvm.pay_method_id = pcm.pay_method_id
WHERE pvm.id IS NULL;
