# AI Cold Email Studio

**Status:** In Progress (shipped; ~50 beta users)

## Purpose

A Flask app for job-seekers that signs in with Gmail or Outlook over OAuth 2.0, generates personalized cold emails, sends them through provider SMTP using XOAUTH2, and tracks open rates in a dashboard. It indexes and retrieves resume context through a vector retrieval layer, and can optionally connect LinkedIn for social posting workflows. Shipped and tested with roughly 50 beta users.

## Methods Used

* Retrieval-augmented generation (RAG) over resume text
* OAuth 2.0 / XOAUTH2 (SASL) authentication
* Open tracking via a 1x1 pixel endpoint
* Scheduled email sending

## Technologies

* Python / Flask
* Google Gemini / OpenAI GPT
* ChromaDB (vector database)
* SQLite / SQLAlchemy
* OAuth2 / XOAUTH2 (SASL)
* Jinja2 / Tailwind CSS

## Required Libraries

* Flask
* SQLAlchemy
* ChromaDB
* sentence-transformers
* Provider SDKs (Google Gemini or OpenAI)

## Project Description

Most AI email generators pass a full resume into the prompt, which spends tokens on content unrelated to the target role. This project retrieves only the relevant parts of the resume before generation:

1. **Chunking:** the resume is broken into semantic fragments.
2. **Embedding:** fragments are converted into vectors using sentence-transformers.
3. **Vector search:** ChromaDB is queried to find the top 3 projects that match the provided job description.
4. **Augmented generation:** only those 3 projects are passed to the LLM, which keeps the output tailored to the role.

### Authentication

Authentication is handled entirely through OAuth 2.0 and XOAUTH2 for Gmail and Outlook, replacing SMTP app passwords. No email passwords are collected or stored. Session cookies are `HttpOnly`, `SameSite=Lax`, and secure by default. Tokens are stored server-side in memory and refreshed on expiry.

### Open tracking

Sent emails embed a 1x1 tracking pixel. When the pixel loads, the open is recorded to a local SQLite analytics store and surfaced in the dashboard.

### Scheduled sending

Emails can be queued to send at chosen times using a SQLite-backed scheduler.

### LinkedIn integration

An optional LinkedIn OAuth connection pulls profile data for personalization and supports posting workflows.

### API endpoints

```
GET  /api/linkedin/auth/start
GET  /api/linkedin/callback
GET  /api/linkedin/status
POST /api/linkedin/post
POST /api/context/index
POST /api/context/retrieve
GET  /api/dashboard/open-rates
GET  /dashboard
```

## To Use

### Prerequisites

* Python 3.10+
* A Gmail or Outlook account with OAuth credentials
* An API key (Gemini or OpenAI)

### Installation

```bash
git clone https://github.com/priyanka-0207/ColdEmailGenerator.git
cd ColdEmailGenerator

python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows

pip install -r requirements.txt
```

### Environment setup

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

### Run the app

```bash
python app.py
```

Then visit `http://localhost:5000` to connect your accounts and start generating. To run the test suite:

```bash
pytest
```

## Limitations

* Tokens are stored in server memory, so they do not survive a restart.
* Resume embeddings are stored locally in ChromaDB, not on a third-party cloud.

## Author

Priyanka Bhutada
