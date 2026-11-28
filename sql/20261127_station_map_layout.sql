-- Station floor map (dashboard Gaming Stations > Map). Additive and nullable:
-- a console without a cell is auto-placed by the dashboard.
BEGIN;
ALTER TABLE consoles ADD COLUMN IF NOT EXISTS map_x integer;
ALTER TABLE consoles ADD COLUMN IF NOT EXISTS map_y integer;
ALTER TABLE consoles DROP CONSTRAINT IF EXISTS consoles_map_cell_range;
ALTER TABLE consoles ADD CONSTRAINT consoles_map_cell_range CHECK (
  (map_x IS NULL AND map_y IS NULL)
  OR (map_x BETWEEN 0 AND 199 AND map_y BETWEEN 0 AND 199)
);
CREATE TABLE IF NOT EXISTS vendor_station_maps (
  vendor_id integer PRIMARY KEY REFERENCES vendors(id) ON DELETE CASCADE,
  zones jsonb NOT NULL DEFAULT '[]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
