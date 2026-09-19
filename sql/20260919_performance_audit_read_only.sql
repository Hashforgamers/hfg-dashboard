-- Diagnostics only: no schema, data or configuration changes.
-- Run against each deployed service database using a read-only monitoring role.
-- Do not wrap existing CREATE INDEX migrations into this script.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT current_database() AS database, version() AS postgres_version;

-- Confirm migrations actually landed, including dynamically generated vendor tables.
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename, indexname;

-- Invalid/incomplete indexes need investigation before being counted as coverage.
SELECT n.nspname AS schema, t.relname AS table_name, i.relname AS index_name,
       x.indisvalid, x.indisready
FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid
JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE NOT x.indisvalid OR NOT x.indisready;

-- Large scans, stale statistics and dead tuples. A small-table scan is not a bug.
SELECT schemaname, relname, n_live_tup, n_dead_tup, seq_scan, seq_tup_read,
       idx_scan, last_analyze, last_autoanalyze, last_autovacuum
FROM pg_stat_user_tables ORDER BY seq_tup_read DESC LIMIT 50;

-- Connection pressure and waits, without exposing query text or customer data.
SELECT application_name, state, wait_event_type, wait_event, count(*) AS connections,
       max(clock_timestamp()-xact_start) AS oldest_transaction
FROM pg_stat_activity WHERE datname=current_database()
GROUP BY application_name, state, wait_event_type, wait_event
ORDER BY connections DESC;

SELECT relname, indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes ORDER BY pg_relation_size(indexrelid) DESC LIMIT 50;
SELECT extname, extversion FROM pg_extension WHERE extname='pg_stat_statements';
COMMIT;
-- If pg_stat_statements is installed, inspect slow normalized queries separately.
-- Use EXPLAIN (ANALYZE, BUFFERS) only on reviewed SELECTs in staging: ANALYZE executes.
-- Prefer measured composite indexes over adding indexes to every filter column.
