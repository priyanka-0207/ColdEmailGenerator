# ColdEmailGenerator

A Flask app that helps job-seekers:

1. connect a Gmail account for free (using app passwords),
2. generate a cold email from resume context,
3. schedule the email to send later.

The UI now uses a **3-page flow**:
- `/connect` → connect Gmail inbox
- `/generate` → generate draft from resume context
- `/schedule` → review + schedule and see recent jobs

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Notes

- Gmail sending uses SMTP + app passwords (free tier).
- Scheduled jobs are stored in `scheduler.db` (SQLite).
- This is a starter project; do not deploy with the default `secret_key`.

## Test

```bash
pip install pytest
pytest
```
