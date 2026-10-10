# Liara deployment notes

This application is a Flask app and is deployed on Liara. Do not use Vercel-specific filesystem assumptions when configuring production.

## Required environment variables

- `SECRET_KEY`: set a long, random secret in Liara's environment variables. The app intentionally refuses to start on Liara with the development default.
- `DATABASE_PATH`: set this to the SQLite database file inside a **persistent, writable Liara disk mount**. Example format only: `/path/to/persistent-mount/kidareh.sqlite3`. Replace it with the actual mount path configured for this app.
- `UPLOAD_FOLDER`: uploads must also live on persistent storage if uploaded images must survive redeploys.

## Capacity and scale

Measured on this codebase with **1,000,000 listings and 100,000 stores** on a
2-CPU / 4 GB machine (SQLite, WAL). These are the numbers to watch when the
catalogue grows:

| Endpoint | Median latency |
| --- | --- |
| `GET /` | 2.5 ms |
| `GET /api/listings` (first page) | 3.5 ms |
| `GET /api/listings` (deep page, keyset) | 2.8 ms |
| `GET /api/listings?q=…` (full text) | 5.9 ms |
| `GET /api/listings?city=…&category=…` | 2.8 ms |
| `GET /api/listings` nearby | 24.7 ms |
| `GET /api/stores` | 1.7 ms |
| `GET /sitemap.xml` | 0.5 ms |

What keeps them there, and what to preserve when changing queries:

- **Pagination is keyset (`before_id`), never `OFFSET`.** An `OFFSET` page at
  the end of a million rows has to walk every skipped row first.
- **Browse indexes carry the sort columns.** Queries sort by
  `featured DESC, id DESC`, so the indexes are
  `(category|city, featured DESC, id DESC)`. Dropping `featured` from an index
  costs 250 ms per query at this scale, because SQLite then has to read every
  matching row to learn whether it is featured before it can sort.
- **Full-text search is windowed.** A popular term can match hundreds of
  thousands of rows; only the newest `FTS_SEARCH_WINDOW` (5,000) matches are
  joined back onto the listings table. That bound is what keeps a search at
  ~6 ms instead of ~200 ms.
- **Store counters use correlated sub-queries**, not `LEFT JOIN … GROUP BY`,
  so a page of 50 stops after 50 rows instead of aggregating the whole table.
- **One database connection per request**, reused across every query in that
  request and closed by the app-context teardown.

Reproduce the numbers with:

```bash
python scripts/scale_profiles.py --listings 1000000 --stores 100000
```

### Database maintenance

```bash
python scripts/maintain_db.py --report    # size and row counts, changes nothing
python scripts/maintain_db.py             # ANALYZE + PRAGMA optimize + checkpoint
python scripts/maintain_db.py --vacuum    # off-hours only: rewrites the file
```

Run `ANALYZE` weekly (cron) and after any bulk import. SQLite plans queries from
the statistics `ANALYZE` collects; without them it guesses, and a wrong guess on
a large table is the difference between an index seek and a full scan. The app
deliberately never runs it on start-up, because on a huge catalogue the scan
costs seconds.

### Rate limits

Write endpoints are limited through a shared, database-backed ledger
(`kidareh/services/rate_limits.py`), so every worker enforces the same budget.
Keys are the signed-in user id, falling back to the client IP; the key is stored
hashed, never raw.

| Scope | Budget | Cooldown |
| --- | --- | --- |
| `listing_create` | 60 / hour | 2 s |
| `message_send` | 120 / hour | 1 s |
| `conversation_create` | 30 / hour | — |
| `store_create` | 5 / hour | — |
| `support_ticket` | 10 / day | — |
| `report_create` | 10 / hour | — |

Rows older than a day are pruned automatically.

## Important upload-path caveat

The current app stores uploaded images under `UPLOAD_FOLDER`, but generates public image URLs under `/static/uploads/<filename>`. If `UPLOAD_FOLDER` is set to a directory outside Flask's static directory, the files may be saved successfully but will not be served from those URLs without a matching media route or reverse-proxy mapping.

Before pointing `UPLOAD_FOLDER` at a separate mount directory, configure the app or Liara routing to serve that directory safely. Do not expose the whole disk mount as a public directory.

## Start-up schema initialization

Every Gunicorn worker runs `initialize_database()` while importing the app. That work is serialized with a dedicated SQLite lock file, `kidareh-migrations.lock`, created next to the configured `DATABASE_PATH`. The lock is released automatically if a worker dies, so there is no stale lock to clear; exclude the file from backups.

Feature tables such as `content_reports` and `otp_rate_limits` are created at start-up too, so no request ever runs schema DDL.

## SQLite and backups

- Keep the database file on a persistent disk, not `/tmp` or the ephemeral application filesystem.
- Back up the database before deploys that include schema changes.
- Do not run multiple app instances with separate local SQLite files; they will show different data. For multi-instance scaling, use a shared database service instead.
- Verify after deployment by creating a test listing, restarting/redeploying, and checking that the listing and its image remain available.

## Health check

Use `/api/health` to confirm the app can connect to its configured database. A successful health check confirms connectivity, not that the disk is persistent or backups are working.


## Six-stage release gate

Run these checks in order before announcing the marketplace ready for customers.

1. **Authentication:** CI must pass the OTP challenge and auth-page tests. In Liara, verify a real SMS request, cooldown/rate-limit responses, successful login, new-user registration, and session continuity. CI does not prove that the SMS provider credentials work.
2. **Seller journey:** verify seller registration, store creation, product creation with and without an image, public product detail, and buyer-to-seller message delivery using two test accounts.
3. **Data and deployment:** set `SECRET_KEY`, `DATABASE_PATH`, and `UPLOAD_FOLDER` to the actual Liara environment and persistent disk mount. Uploads are stored sharded (`UPLOAD_FOLDER/ab/abcd123….png`) and served by the `/static/uploads/<path:filename>` route, which validates the extension and rejects path traversal. Confirm the database and uploads remain after a redeploy; the health endpoint cannot prove that a disk is persistent.
4. **Mobile and PWA:** test at a narrow viewport and on a real phone; check bottom navigation, product cards, sign-in forms, install prompt, standalone launch, and service-worker cache refresh.
5. **Payments and administration:** in a controlled test account, check each package/order state, provider failure and cancellation, verified callback, duplicate callback handling, admin authorization, support reply, and reporting. Never use a real charge for a smoke test.
6. **Release acceptance:** require a green GitHub Actions run, no unresolved critical browser-console errors, successful Liara health check, and recorded confirmation of the manual checks above.

### What the automated health check proves

`/api/health` checks database connectivity and whether the configured upload directory exists and is writable. It deliberately does not expose filesystem paths or claim to verify persistent-disk attachment, backups, restore capability, SMS delivery, or payment settlement. Those require deployment-level checks.
