# Deploy UzhavanGo on Render

## 1) Create services

1. Create a new PostgreSQL database in Render.
2. Create a new Web Service from this repository.

## 2) Build and start commands

- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
gunicorn wsgi:app
```

(`Procfile` already contains `web: gunicorn wsgi:app`.)

## 3) Environment variables

Set these in Render:

- `FLASK_ENV=production`
- `SECRET_KEY=<strong-random-secret>`
- `DATABASE_URL=<Render PostgreSQL internal URL>`
- `SESSION_COOKIE_SECURE=true`
- `MAX_UPLOAD_MB=5`
- `UPLOAD_DIR=static/uploads`
- `RATELIMIT_STORAGE_URI=memory://` (or Redis URL if available)
- `RATELIMIT_DEFAULT=200 per day;80 per hour`
- `SENTRY_DSN=<optional>`

## 4) Database migration steps

Run these one-time commands in a Render shell:

```bash
python scripts/migrate_sqlite_inplace.py --db instance/uzhavango.db
flask db upgrade
```

For PostgreSQL-first deployments, `flask db upgrade` is the primary path.

## 5) Uploads and media notes

- Local uploads are stored under `static/uploads`.
- For multi-instance production, move uploads to S3-compatible storage.

## 6) Security checklist

- Keep `DEBUG` disabled (`FLASK_ENV=production`).
- Use HTTPS-only cookies (`SESSION_COOKIE_SECURE=true`).
- Rotate `SECRET_KEY` securely.
- Configure Sentry for production error tracking.
