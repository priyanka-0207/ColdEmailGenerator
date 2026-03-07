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

## Deploy (Render quick start)

This repo includes `render.yaml` + `Procfile` for one-click style deployment.

1. Push repo to GitHub.
2. Create a new **Web Service** on Render from the repo.
3. Render will use:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn -w 1 -k gthread -b 0.0.0.0:$PORT app:app`
4. Set env vars:
   - `SECRET_KEY` (required)
   - `RUN_SCHEDULER=true`
   - `SESSION_COOKIE_SECURE=true` (for HTTPS)
   - `FLASK_DEBUG=false`

## Notes

- Gmail sending uses SMTP + app passwords (free tier).
- Scheduled jobs are stored in `scheduler.db` (SQLite).
- For this in-process scheduler design, run a single web instance (`-w 1`) to avoid duplicate sends.
- For larger scale, migrate queueing/storage to dedicated worker + Postgres/Redis.

## Test

```bash
pip install pytest
pytest
```
