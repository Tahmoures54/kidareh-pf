# Liara deployment notes

This application is a Flask app and is deployed on Liara. Do not use Vercel-specific filesystem assumptions when configuring production.

## Required environment variables

- `SECRET_KEY`: set a long, random secret in Liara's environment variables. The app intentionally refuses to start on Liara with the development default.
- `DATABASE_PATH`: set this to the SQLite database file inside a **persistent, writable Liara disk mount**. Example format only: `/path/to/persistent-mount/kidareh.sqlite3`. Replace it with the actual mount path configured for this app.
- `UPLOAD_FOLDER`: uploads must also live on persistent storage if uploaded images must survive redeploys.

## Important upload-path caveat

The current app stores uploaded images under `UPLOAD_FOLDER`, but generates public image URLs under `/static/uploads/<filename>`. If `UPLOAD_FOLDER` is set to a directory outside Flask's static directory, the files may be saved successfully but will not be served from those URLs without a matching media route or reverse-proxy mapping.

Before pointing `UPLOAD_FOLDER` at a separate mount directory, configure the app or Liara routing to serve that directory safely. Do not expose the whole disk mount as a public directory.

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
3. **Data and deployment:** set `SECRET_KEY`, `DATABASE_PATH`, and `UPLOAD_FOLDER` to the actual Liara environment and persistent disk mount. The explicit `/static/uploads/<filename>` route now serves supported image files from the configured upload folder. Confirm the database and uploads remain after a redeploy; the health endpoint cannot prove that a disk is persistent.
4. **Mobile and PWA:** test at a narrow viewport and on a real phone; check bottom navigation, product cards, sign-in forms, install prompt, standalone launch, and service-worker cache refresh.
5. **Payments and administration:** in a controlled test account, check each package/order state, provider failure and cancellation, verified callback, duplicate callback handling, admin authorization, support reply, and reporting. Never use a real charge for a smoke test.
6. **Release acceptance:** require a green GitHub Actions run, no unresolved critical browser-console errors, successful Liara health check, and recorded confirmation of the manual checks above.

### What the automated health check proves

`/api/health` checks database connectivity and whether the configured upload directory exists and is writable. It deliberately does not expose filesystem paths or claim to verify persistent-disk attachment, backups, restore capability, SMS delivery, or payment settlement. Those require deployment-level checks.
