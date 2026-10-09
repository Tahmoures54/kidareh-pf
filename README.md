# Kidareh PF

A lightweight Persian marketplace starter built with Flask, server-rendered HTML, CSS, and vanilla JavaScript.

## Features

- Responsive Persian RTL homepage
- Search and category filters for demo listings
- Optional listing photos (JPG, PNG, WebP; maximum 4 MiB) with server-side signature and size checks
- Optional seller mobile number for coordinating an in-person visit, validated and normalized to Iranian mobile format
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

- `SECRET_KEY`: set a strong secret in production.
- `DATABASE_PATH`: optional path to a persistent SQLite file. Defaults to `instance/kidareh.sqlite3`.
- `PORT`: optional server port, defaults to `5000`.

## Production notes

Use a production WSGI server (for example Gunicorn), configure a persistent disk for SQLite or move to PostgreSQL as traffic grows, and add real authentication, moderation, rate limiting, and persistent upload storage before accepting real users. Seller contact numbers are public in listing details in this demo, so do not enter real personal numbers until authentication, ownership controls, and privacy controls are implemented. Uploaded images are stored under `static/uploads` by default; configure `UPLOAD_FOLDER` and durable storage on deployment. The included listings are clearly demo content.
