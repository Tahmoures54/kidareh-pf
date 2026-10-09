# Kidareh PF

A lightweight Persian marketplace starter built with Flask, server-rendered HTML, CSS, and vanilla JavaScript.

## Features

- Responsive Persian RTL homepage
- Search and category filters for demo listings
- Flask JSON endpoints: `/api/health`, `/api/categories`, `/api/listings`
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

Use a production WSGI server (for example Gunicorn), configure a persistent disk for SQLite or move to PostgreSQL as traffic grows, and add real authentication, moderation, and upload handling before accepting real users or transactions. The included listings are clearly demo content.
