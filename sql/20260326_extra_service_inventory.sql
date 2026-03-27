-- Extra service inventory support (shared schema)
ALTER TABLE extra_service_menus
ADD COLUMN IF NOT EXISTS stock_quantity INTEGER;

ALTER TABLE extra_service_menus
ADD COLUMN IF NOT EXISTS stock_unit VARCHAR(32) NOT NULL DEFAULT 'units';

ALTER TABLE extra_service_menus
ADD COLUMN IF NOT EXISTS low_stock_threshold INTEGER NOT NULL DEFAULT 0;

