# ColdEmailGenerator

A Flask app that helps job-seekers:

1. connect a Gmail account for free (using app passwords),
2. generate a cold email from resume context,
3. schedule the email to send later.

The UI uses a **3-page flow**:
- `/connect` → connect Gmail inbox
- `/generate` → generate draft from resume context
- `/schedule` → review + schedule and see recent jobs

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:5000`.

## Ship it (Render quick start)

This repo includes `render.yaml` + `Procfile` for deployment.

1. Push repo to GitHub.
2. Create a **Web Service** on Render from this repo.
3. Render will use:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn -w 1 -k gthread -b 0.0.0.0:$PORT app:app`
   - Health check: `/healthz`
4. Set env vars:
   - `SECRET_KEY` (required)
   - `RUN_SCHEDULER=true`
   - `SESSION_COOKIE_SECURE=true` (HTTPS)
   - `FLASK_DEBUG=false`

### Recommended first production test
1. Connect Gmail with app password.
2. Generate a draft.
3. Schedule an email 2–3 minutes in the future.
4. Confirm status changes from `scheduled` to `sent` in the Schedule page.

## Docker deploy option

```bash
docker build -t cold-email-generator .
docker run --rm -p 5000:5000 \
  -e SECRET_KEY='replace-me' \
  -e RUN_SCHEDULER=true \
  -e SESSION_COOKIE_SECURE=false \
  cold-email-generator
```

## Notes

- Gmail sending uses SMTP + app passwords (free tier).
- Scheduled jobs are stored in `scheduler.db` (SQLite).
- This scheduler is in-process, so run a single app worker (`-w 1`) to avoid duplicate sends.
- For larger scale, use a dedicated worker + Postgres/Redis.

## Test

```bash
pip install pytest
pytest
```
