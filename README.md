# 🚀 AI Cold Email Studio

A Flask app for job-seekers to:

1. sign in with Gmail or Outlook using OAuth 2.0,
2. generate personalized cold emails,
3. send emails via provider SMTP using XOAUTH2,
4. track open rates in a dashboard,
5. index/retrieve resume context with a lightweight vector-style retrieval layer,
6. optionally connect LinkedIn for social posting workflows.

## ✨ Key Features

  * **Smart Context Retrieval (RAG):** Uses a vector database (**ChromaDB**) to inject only the most relevant parts of your resume into the LLM prompt.
  * **Secure Authentication:** Fully migrated from insecure SMTP passwords to **OAuth2 & XOAuth2** for Gmail and Outlook.
  * **LinkedIn Integration:** Connect your professional profile to pull live data for outreach personalization.
  * **Open Tracking:** Real-time dashboard to monitor when your emails are opened via a 1x1 tracking pixel.
  * **Scheduled Sending:** Queue your emails to be sent at optimal times using a robust SQLite-backed scheduler.

-----

## 🧠 The Tech Stack

| Component | Technology |
| :--- | :--- |
| **Backend** | Python / Flask |
| **AI/LLM** | Google Gemini / OpenAI GPT |
| **Vector DB** | ChromaDB |
| **Database** | SQLite / SQLAlchemy |
| **Auth** | OAuth2 / XOAuth2 (SASL) |
| **Frontend** | Jinja2 / Tailwind CSS |

-----

## 🛠️ Technical Deep Dive: Why RAG?

Most "AI generators" simply dump a full resume into a prompt, leading to "token bloat" and irrelevant content. This project solves that by:

1.  **Chunking:** Breaking your resume into semantic fragments.
2.  **Embedding:** Converting fragments into vectors using `sentence-transformers`.
3.  **Vector Search:** Querying **ChromaDB** to find the top 3 projects that match the *specific* Job Description provided.
4.  **Augmented Generation:** Passing only those 3 relevant projects to the LLM, ensuring a highly tailored and "human" tone.

-----

## 🚀 Getting Started

### 1\. Prerequisites

  * Python 3.10+
  * A Gmail or Outlook account (with OAuth Credentials)
  * An API Key (Gemini or OpenAI)

### 2\. Installation

```bash
# Clone the repository
git clone https://github.com/priyanka-0207/ColdEmailGenerator.git
cd ColdEmailGenerator

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3\. Environment Setup

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

### 4\. Run the App

```bash
pytest
```

Visit `http://localhost:5000` to connect your accounts and start generating.

-----

## 🛡️ Security & Privacy

  * **No Stored Passwords:** We use OAuth2 tokens; your email password never touches our database.
  * **Local Processing:** Resume embeddings are stored locally in ChromaDB, not on a third-party cloud.

-----
