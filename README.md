# Kidareh PF

A lightweight storefront-first local marketplace built with Flask, server-rendered HTML, CSS, and vanilla JavaScript. Shoppers can browse products and store windows without an account; sellers sign in to create a storefront and add products.

## Features

- Responsive Persian RTL storefront-first homepage
- Public storefront directory with search and individual storefront pages
- Guest product browsing and device-local saved products
- Signed-in shoppers can follow/unfollow storefronts; followed stores are persisted
- Sellers create one storefront per account and add products to their own storefront
- Search and category filters for products
- Optional listing photos (JPG, PNG, WebP; maximum 4 MiB) with server-side signature and size checks
- Phone-first signup/login with Kavenegar OTP, arithmetic CAPTCHA, and recorded terms acceptance
- Owner-only listing edit and delete operations
- Optional seller mobile number for coordinating an in-person visit, validated and normalized to Iranian mobile format; excluded from public search results
- Flask JSON endpoints for public stores, store details, follows, saved products, categories, and product browsing
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

Use a production WSGI server (for example Gunicorn), configure a persistent disk for SQLite or move to PostgreSQL as traffic grows, and add persistent rate limiting, moderation, account recovery, and privacy controls for revealing seller contact before broad public launch. This repository currently writes SQLite data to `instance/` and uploads to `static/uploads`; these paths are not durable storage on Vercel Functions. Do not treat a Vercel deployment as production-ready for user-generated data until the database and images are moved to persistent services. Store browsing is public; following a store requires an account. Product saves use browser-local storage for guests. The project has not undergone a security audit. The included listings are demo content. Store browsing is public; following a store requires an account. Product saves currently use browser-local storage for guests. Passwords are hashed and account sessions are CSRF-protected, but this is still an initial implementation and has not undergone a security audit. Uploaded images are stored under `static/uploads` by default; configure `UPLOAD_FOLDER` and durable storage on deployment. The included listings are clearly demo content.

## Backend architecture

The Flask backend is organized as a small application package with domain-focused Blueprints:

```text
app.py                       # WSGI entry point and compatibility exports
kidareh/
  __init__.py                # create_app() and Blueprint registration
  core.py                    # database initialization, shared helpers, categories
  routes/
    __init__.py
    pages.py                 # HTML page routes
    auth.py                  # signup, login, session, seller role
    stores.py                # storefronts, follows, saved-product API
    listings.py              # catalog, listing CRUD, image validation
    system.py                # health endpoint
```

The public URL paths remain unchanged, so existing frontend requests and the Gunicorn `app:app` entry point continue to work. Each Blueprint owns one domain; shared database/session helpers live in `kidareh/core.py`. The application factory `create_app(test_config=None)` makes isolated configuration and testing easier.


## Phone OTP configuration

Set `KAVENEGAR_API_KEY` and `KAVENEGAR_VERIFY_TEMPLATE` to enable live SMS verification. OTP codes expire after five minutes, with a per-session 45-second resend cooldown and five failed attempts allowed. Production deployment still needs persistent cross-worker rate limiting.
