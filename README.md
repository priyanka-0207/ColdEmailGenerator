# ColdEmailGenerator

A simple Flask app that helps job-seekers:

1. connect a Gmail or Outlook account for free (using app passwords),
2. generate a cold email from resume context,
3. schedule the email to send later.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

## Notes

- Gmail and Outlook sending uses SMTP + app passwords (free tiers).
- Scheduled jobs are stored in `scheduler.db` (SQLite).
- This is a starter project; do not deploy with the default `secret_key`.

## Test

```bash
pip install pytest
pytest
```
