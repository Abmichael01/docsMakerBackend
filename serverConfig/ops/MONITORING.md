# Monitoring — lightweight setup for the Contabo VPS

Three layers, all optional but all cheap:

## 1. Netdata on the Contabo HOST (not inside Dokploy)

Runs on the VPS itself, sees every container, Postgres, Redis, nginx (Traefik),
and the host. Resource use is tiny (~50MB RAM).

```bash
# On the Contabo VPS (host shell, not a container):
bash <(curl -SsL https://get.netdata.cloud/kickstart.sh) \
    --no-updates --stable-channel --disable-telemetry --dont-wait
```

Bind it to localhost only (don't expose the dashboard publicly):

```bash
sudo sed -i 's/# bind socket to IP = \*/bind socket to IP = 127.0.0.1/' \
    /etc/netdata/netdata.conf
sudo systemctl restart netdata
```

View via SSH tunnel:
```bash
ssh -L 19999:127.0.0.1:19999 user@<your-contabo-ip>
# then open http://localhost:19999
```

**What to watch:**
- `postgresql.connections_utilization` — alert when > 70%
- `pgbouncer.cl_waiting` — clients waiting for a server connection. Steady-state should be 0
- `redis.clients` — connected clients
- `docker.containers.<name>.cpu/memory` — per-service usage

## 2. pg_stat_statements — slow query log

Already set up by `postgresql.tuning.conf` and `pg_stat_statements.sql`.
Inspect with:

```sql
SELECT
  left(regexp_replace(query, '\s+', ' ', 'g'), 120) AS q,
  calls,
  round(mean_exec_time::numeric, 2)   AS mean_ms,
  round(total_exec_time::numeric, 0)  AS total_ms,
  rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

Run weekly. Anything with `mean_ms > 500` is a fix candidate.

## 3. Django logging — turn on only when investigating

In `serverConfig/settings.py`, **don't** leave DB query logging on permanently
(it doubles log volume). Add this conditional block — toggle via env var:

```python
if os.getenv("SQL_DEBUG") == "1":
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "loggers": {
            "django.db.backends": {"handlers": ["console"], "level": "DEBUG"},
        },
    }
```

In Dokploy, set `SQL_DEBUG=1` on a single service for a few minutes when
you want to see every query, then unset and redeploy.

## 4. Sentry (already configured)

You already have `sentry_sdk` initialized in `settings.py`. After deploying
the fixes, watch the Sentry dashboard for:

- A drop in `django.db.utils.OperationalError: too many clients already`
- Any *new* error spike (the WS auth caching, the AI stream `finally`, and
  the N+1 rewrite are the most likely places to regress)

Set a Sentry alert for any new occurrence of `OperationalError` after
deploy — should be near-zero post-rollout.

## Quick health snapshot — copy/paste anytime

Run from any Dokploy service shell (pick celery, it has psql-able env):

```bash
# 1. Pool occupancy from PgBouncer's admin view
psql "postgres://$DB_USER:$DB_PASSWORD@sharptoolz-pgbouncer:6432/pgbouncer" \
  -c "SHOW POOLS;" -c "SHOW STATS;"

# 2. Real Postgres backends
psql "$DATABASE_URL" -c "
  SELECT state, count(*)
  FROM pg_stat_activity
  WHERE datname = 'sharptoolz'
  GROUP BY state ORDER BY 2 DESC;"

# 3. Redis pressure
redis-cli -u "$REDIS_URL" INFO clients | grep -E "connected_clients|blocked"
redis-cli -u "$REDIS_URL" INFO memory | grep -E "used_memory_human|mem_fragmentation"
```

If you save this as `ops-snapshot.sh` and run it during incidents, the
three blocks tell you whether the pressure is at the app, the pooler, or
Postgres itself.
