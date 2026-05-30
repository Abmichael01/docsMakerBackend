-- Enable Postgres query-stats extension. Run ONCE as superuser:
--   sudo -u postgres psql -d sharptoolz -f ops/pg_stat_statements.sql
--
-- Prerequisite: postgresql.conf must include
--   shared_preload_libraries = 'pg_stat_statements'
-- and Postgres must have been RESTARTED (not just reloaded) after that change.
-- See ops/postgresql.tuning.conf.

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Reset accumulated stats so we measure from a clean baseline:
SELECT pg_stat_statements_reset();

-- Quick smoke test: should return a row.
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_stat_statements';

-- After running the app for a while, find the worst queries:
--
--   SELECT
--     left(regexp_replace(query, '\s+', ' ', 'g'), 120) AS q,
--     calls,
--     round(mean_exec_time::numeric, 2)   AS mean_ms,
--     round(total_exec_time::numeric, 0)  AS total_ms,
--     rows
--   FROM pg_stat_statements
--   ORDER BY total_exec_time DESC
--   LIMIT 20;
--
-- Look for: high mean_ms (slow per call) or high total_ms (called often).
-- The N+1 fix from this PR should make CampaignViewSet.stats disappear from
-- the top of that list.
