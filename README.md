# ColdEmailGenerator

A small side project built to help job-seekers with practical outreach workflows:

1. sign in with Gmail or Outlook using OAuth 2.0,
2. generate personalized cold emails,
3. send emails via provider SMTP using XOAUTH2,
4. track open rates in a dashboard,
5. index/retrieve resume context with a lightweight vector-style retrieval layer,
6. optionally connect LinkedIn for social posting workflows.

Maintained by Priyanka Bhutada.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000.

## OAuth setup

```bash
export SECRET_KEY="replace-with-a-long-random-value"
export OAUTH_CALLBACK_URL="http://localhost:5000/api/oauth/callback"
export TRACKING_BASE_URL="http://localhost:5000"

# Google OAuth app
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."

# Microsoft OAuth app
export MICROSOFT_CLIENT_ID="..."
export MICROSOFT_CLIENT_SECRET="..."

# LinkedIn OAuth app
export LINKEDIN_CLIENT_ID="..."
export LINKEDIN_CLIENT_SECRET="..."
export LINKEDIN_CALLBACK_URL="http://localhost:5000/api/linkedin/callback"
# Needed only if publishing posts
export LINKEDIN_MEMBER_URN="urn:li:person:..."
```

## New APIs

- `GET /api/linkedin/auth/start`
- `GET /api/linkedin/callback`
- `GET /api/linkedin/status`
- `POST /api/linkedin/post`
- `POST /api/context/index`
- `POST /api/context/retrieve`
- `GET /api/dashboard/open-rates`
- `GET /dashboard`

## Security notes

- Authentication uses OAuth 2.0 (no app passwords collected).
- Session cookies are `HttpOnly`, `SameSite=Lax`, secure by default.
- Tokens are stored server-side in memory and refreshed on expiry.
- Open tracking uses a 1x1 pixel endpoint and local SQLite analytics.

## Test

```bash
pytest
```
