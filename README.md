# Kidareh PF

A lightweight Persian marketplace starter built with Flask, server-rendered HTML, CSS, and vanilla JavaScript.

## Features

- Responsive Persian RTL homepage
- Search and category filters for demo listings
- Optional listing photos (JPG, PNG, WebP; maximum 4 MiB) with server-side signature and size checks
- Account signup and login with hashed passwords and CSRF-protected write requests
- Owner-only listing edit and delete operations
- Optional seller mobile number for coordinating an in-person visit, validated and normalized to Iranian mobile format; excluded from public search results
- Flask JSON endpoints: `/api/health`, `/api/categories`, `/api/listings`, `/api/listings/<id>`
- Local SQLite database with safe first-run initialization and demo listings
- No React, Node.js build step, or external runtime dependency beyond Flask

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Configuration

- `SECRET_KEY`: set a strong, random secret in production; do not use the development fallback on a public deployment.
- `DATABASE_PATH`: optional path to a persistent SQLite file. Defaults to `instance/kidareh.sqlite3`.
- `PORT`: optional server port, defaults to `5000`.

## Production notes

Use a production WSGI server (for example Gunicorn), configure a persistent disk for SQLite or move to PostgreSQL as traffic grows, and add login rate limiting, phone verification, moderation, account recovery, privacy controls for revealing seller contact, and persistent upload storage before broad public launch. Passwords are hashed and account sessions are CSRF-protected, but this is still an initial implementation and has not undergone a security audit. Uploaded images are stored under `static/uploads` by default; configure `UPLOAD_FOLDER` and durable storage on deployment. The included listings are clearly demo content.
