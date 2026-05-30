# Rollout plan — Dokploy / Coolify

Goal: stop "too many clients already" without downtime. Each step is
independently rollback-able. Do **not** skip ahead — the order is what makes
this safe.

> If anything goes sideways at any step, the rollback is always: revert the
> last Dokploy change, redeploy, move on.

---

## Step 0 — Merge the local code fixes (already done in this PR)

These are pure code, no infra dependency. Deploying them via your existing
sharptoolz-web service is safe by itself:

- `frontend/src/hooks/useWebSocketClient.ts` — true exp backoff + jitter + visibility
- `frontend/src/hooks/usePresence.ts` — removed broken `pagehide` handler
- `backend/accounts/authentication.py` — WS JWT user lookup cached 30s
- `backend/analytics/views.py` — `CampaignViewSet.stats` de-N+1
- `backend/api/views/ai_chat/__init__.py` — `close_old_connections()` in `finally`
- `backend/serverConfig/settings.py` — `django_extensions` only in DEBUG

**Deploy and watch.** You should already see fewer "too many clients" errors
just from this (the JWT cache + N+1 fix alone cut a lot of DB pressure).

---

## Step 1 — Add the sharptoolz-pgbouncer service in Dokploy

1. In Dokploy, create a new application:
   - **Source:** same git repo
   - **Build type:** Dockerfile
   - **Dockerfile path:** `backend/Dockerfile.pgbouncer`
   - **Service name (slug):** `sharptoolz-pgbouncer` (or whatever — but remember it for the DATABASE_URL)
2. **Environment** tab — set:
   ```
   DB_HOST=<your current Postgres host>
   DB_PORT=5432
   DB_USER=<existing PG user>
   DB_PASSWORD=<existing PG password>
   DB_NAME=sharptoolz
   POOL_MODE=transaction
   DEFAULT_POOL_SIZE=25
   MAX_CLIENT_CONN=400
   ```
3. **Networking:** internal port `6432`. Do NOT expose to the public internet.
4. **Deploy.** Check logs — PgBouncer should log
   `PgBouncer 1.x ... listening on 0.0.0.0:6432`.

**Verify connectivity** from any other service (open a shell into
sharptoolz-celery via Dokploy UI):
```bash
apt-get update && apt-get install -y postgresql-client
psql "postgres://$DB_USER:$DB_PASSWORD@sharptoolz-pgbouncer:6432/sharptoolz" -c "SELECT 1;"
```
If that returns `1`, PgBouncer is healthy. **Nothing is using it yet** — your
app still talks directly to Postgres on port 5432.

**Rollback if needed:** delete the sharptoolz-pgbouncer service. Zero impact
on production.

---

## Step 2 — Switch Django to PgBouncer (atomic flip)

Two changes go together — apply them in one Dokploy redeploy across **all**
DB-using services (web, ws, worker, beat) so they all switch at once.

### 2a. Code change (one commit)

In `backend/serverConfig/settings.py`, inside the `if ENV == "production" and DATABASE_URL:` block, change:

```python
'CONN_MAX_AGE': DB_CONN_MAX_AGE,
```
to:
```python
'CONN_MAX_AGE': 0,                       # PgBouncer pools for us
'DISABLE_SERVER_SIDE_CURSORS': True,     # required for transaction pooling
```

Push.

### 2b. Env var change

In Dokploy, on **each** of `sharptoolz-web`, `sharptoolz-celery`,
`sharptoolz-beat`, change `DATABASE_URL` from:
```
postgres://USER:PASS@<old-host>:5432/sharptoolz
```
to:
```
postgres://USER:PASS@sharptoolz-pgbouncer:6432/sharptoolz
```

### 2c. Redeploy all four

Hit "Redeploy" on web → celery → beat. Order doesn't matter much (no schema
change), but redeploy them within a few minutes of each other so you don't
run mixed states for long.

**Verify** in Postgres (any psql admin session):
```sql
SELECT application_name, count(*)
FROM pg_stat_activity
GROUP BY 1 ORDER BY 2 DESC;
```
You should see most connections now come from `pgbouncer` (or no app_name),
and the count to Postgres should drop to ~30 from whatever it was.

**Rollback:** revert the env var on each service back to the direct
`:5432` URL and redeploy. The code change in 2a is forward-compatible
(CONN_MAX_AGE=0 + DISABLE_SERVER_SIDE_CURSORS=True works without
PgBouncer too — you just lose connection reuse, which is fine for the
revert window).

---

## Step 3 — Add sharptoolz-ws as a separate Dokploy service

This isolates WebSocket traffic so a WS burst can't starve HTTP workers.

1. New Dokploy application:
   - **Source:** same repo
   - **Dockerfile path:** `backend/Dockerfile.ws`
   - **Service name:** `sharptoolz-ws`
   - **Internal port:** `8000`
2. **Environment:** same vars as sharptoolz-web (use Dokploy's
   "Shared environment" if available, or copy them).
3. **Traefik routing** — this is the critical part:
   - **Domain:** same as your web service (e.g. `api.sharptoolz.com`)
   - **Path prefix:** `/ws`
   - **Priority:** `100` (any number > sharptoolz-web's priority — Dokploy
     defaults to 0, so 100 is plenty)
4. **Deploy.**

While both services are running, `/ws/*` traffic flows to Daphne, and
everything else still flows to your existing sharptoolz-web. **No CMD change
yet on the web service** — the ASGI worker there is still happily serving WS,
it just won't get any because Traefik's path rule wins.

**Verify** in the browser DevTools Network tab:
- HTTP requests show as routed to your web container
- WS connections show as routed to the ws container (check container hostname
  in Dokploy logs)

**Rollback:** delete the sharptoolz-ws service. Traffic falls back to the
existing web service automatically because the path rule disappears.

---

## Step 4 — Slim sharptoolz-web down to HTTP-only

Once Step 3 has been stable for ~24h:

In `backend/Dockerfile`, change the final CMD from:
```dockerfile
CMD ["gunicorn", "serverConfig.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300"]
```
to:
```dockerfile
CMD ["gunicorn", "serverConfig.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "gthread", "--threads", "4", \
     "--max-requests", "1000", "--max-requests-jitter", "100", \
     "--timeout", "60", "--graceful-timeout", "30", \
     "--keep-alive", "5"]
```

Why: WSGI sync workers are cheaper than ASGI uvicorn workers for plain JSON
HTTP. `gthread` + 4 threads gives us 12 concurrent in-flight requests across
3 workers — well within PgBouncer's `DEFAULT_POOL_SIZE=25`.

Redeploy sharptoolz-web only.

**Verify**: requests still serve correctly. If anything breaks (e.g. an
endpoint we missed that uses async features), revert the CMD line.

---

## Step 5 — Tune the worker

In Dokploy, on `sharptoolz-celery`:
- Set env var `CELERY_CONCURRENCY=2` (your Dockerfile.worker defaults to 4).

Redeploy. This caps the worker side of the DB budget at 2 connections.

---

## Step 6 — Postgres-side tuning (only if you manage your own PG)

Skip if Postgres is a managed Dokploy service or external managed DB.

```bash
# On the Postgres host:
sudo nano /etc/postgresql/<version>/main/postgresql.conf
# Append the contents of ops/postgresql.tuning.conf to the end of the file.
sudo systemctl reload postgresql

# Enable pg_stat_statements:
sudo -u postgres psql -d sharptoolz -f ops/pg_stat_statements.sql
# Note: also needs 'shared_preload_libraries = pg_stat_statements' set in
# postgresql.conf and a full restart (not reload).
```

---

## Step 7 — Monitoring

Follow `MONITORING.md`. Netdata can run on the Contabo host (not inside
Dokploy) and will auto-detect both the Docker containers and Postgres.

---

## Final connection budget after all steps

| Component                   | Max DB conns to PgBouncer |
|-----------------------------|---------------------------|
| sharptoolz-web (3w × 4t)    | 12                        |
| sharptoolz-ws (Daphne, 10 executor threads) | ≤ 10        |
| sharptoolz-celery (concurrency 2) | 2                   |
| sharptoolz-beat             | 1                         |
| **Total**                   | **≤ 25**                  |

PgBouncer with `DEFAULT_POOL_SIZE=25` and `RESERVE_POOL_SIZE=5` will use at
most 30 real Postgres backends. With Postgres `max_connections=100`, you have
a **70-connection headroom** for psql admin sessions, ad-hoc scripts, and
multi-replica scaling later.
