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
