import base64
import hashlib
import os
import smtplib
import sqlite3
import threading
import time
from collections import Counter, defaultdict, deque
from email.message import EmailMessage
from math import sqrt
from secrets import token_urlsafe
from urllib.parse import urlencode

import requests
from flask import Flask, Response, jsonify, redirect, render_template, request, session

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
    PERMANENT_SESSION_LIFETIME=1800,
)

OAUTH_CALLBACK_URL = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:5000/api/oauth/callback")
LINKEDIN_CALLBACK_URL = os.getenv("LINKEDIN_CALLBACK_URL", "http://localhost:5000/api/linkedin/callback")
TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://localhost:5000")
ANALYTICS_DB = os.getenv("ANALYTICS_DB", "analytics.db")

OAUTH_CONFIG = {
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["openid", "email", "profile", "https://mail.google.com/"],
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
    },
    "outlook": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scopes": [
            "openid",
            "email",
            "offline_access",
            "https://outlook.office.com/SMTP.Send",
            "https://graph.microsoft.com/User.Read",
        ],
        "client_id": os.getenv("MICROSOFT_CLIENT_ID", ""),
        "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", ""),
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
    },
}

LINKEDIN_CONFIG = {
    "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
    "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
    "client_id": os.getenv("LINKEDIN_CLIENT_ID", ""),
    "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET", ""),
    "scopes": ["openid", "profile", "w_member_social", "email"],
    "api_base": "https://api.linkedin.com/v2",
}

SMTP_SESSION_STORE: dict[str, dict[str, str | float]] = {}
SMTP_STORE_LOCK = threading.Lock()
MAX_STORED_SMTP_SESSIONS = 1000

AUTH_WINDOW_SECONDS = 300
MAX_AUTH_ATTEMPTS_PER_WINDOW = 8
AUTH_ATTEMPTS: defaultdict[str, deque[float]] = defaultdict(deque)
AUTH_ATTEMPTS_LOCK = threading.Lock()

# Vector-like resume context index (lightweight local store).
VECTOR_INDEX: defaultdict[str, list[dict]] = defaultdict(list)
VECTOR_LOCK = threading.Lock()


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(ANALYTICS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_events (
                message_id TEXT PRIMARY KEY,
                sender_email TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                sent_at INTEGER NOT NULL,
                opens INTEGER NOT NULL DEFAULT 0,
                last_opened_at INTEGER
            )
            """
        )


_init_db()


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _auth_rate_limited(ip: str) -> bool:
    now = time.time()
    with AUTH_ATTEMPTS_LOCK:
        attempts = AUTH_ATTEMPTS[ip]
        while attempts and attempts[0] <= now - AUTH_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= MAX_AUTH_ATTEMPTS_PER_WINDOW:
            return True
        attempts.append(now)
        return False


def _prune_smtp_store_if_needed() -> None:
    with SMTP_STORE_LOCK:
        while len(SMTP_SESSION_STORE) > MAX_STORED_SMTP_SESSIONS:
            oldest_key = next(iter(SMTP_SESSION_STORE))
            del SMTP_SESSION_STORE[oldest_key]


def _set_auth_session(provider: str, email: str, token_data: dict) -> None:
    session_key = token_urlsafe(24)
    now = time.time()
    with SMTP_STORE_LOCK:
        SMTP_SESSION_STORE[session_key] = {
            "provider": provider,
            "email": email,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", ""),
            "expires_at": now + int(token_data.get("expires_in", 3600)),
        }
    _prune_smtp_store_if_needed()
    session["smtp_key"] = session_key


def _clear_auth_session() -> None:
    smtp_key = session.pop("smtp_key", None)
    if smtp_key:
        with SMTP_STORE_LOCK:
            SMTP_SESSION_STORE.pop(smtp_key, None)


def _get_auth_session() -> dict | None:
    smtp_key = session.get("smtp_key")
    if not smtp_key:
        return None
    with SMTP_STORE_LOCK:
        data = SMTP_SESSION_STORE.get(smtp_key)
        return dict(data) if data else None


def _pkce_pair() -> tuple[str, str]:
    verifier = token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _xoauth2_login(server: smtplib.SMTP, email: str, access_token: str) -> None:
    auth_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
    xoauth_b64 = base64.b64encode(auth_string.encode()).decode()
    code, response = server.docmd("AUTH", f"XOAUTH2 {xoauth_b64}")
    if code != 235:
        raise smtplib.SMTPAuthenticationError(code, response)


def _fetch_profile_email(provider: str, access_token: str) -> str | None:
    cfg = OAUTH_CONFIG[provider]
    response = requests.get(cfg["userinfo_url"], headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if not response.ok:
        return None
    data = response.json()
    if provider == "gmail":
        return data.get("email")
    return data.get("mail") or data.get("userPrincipalName")


def _refresh_access_token(auth_session: dict) -> dict | None:
    provider = auth_session["provider"]
    cfg = OAUTH_CONFIG[provider]
    refresh_token = auth_session.get("refresh_token")
    if not refresh_token:
        return None

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
    }
    if provider == "outlook":
        payload["scope"] = " ".join(cfg["scopes"])

    response = requests.post(cfg["token_url"], data=payload, timeout=10)
    if not response.ok:
        return None
    token_data = response.json()

    updated = dict(auth_session)
    updated["access_token"] = token_data["access_token"]
    updated["refresh_token"] = token_data.get("refresh_token", refresh_token)
    updated["expires_at"] = time.time() + int(token_data.get("expires_in", 3600))

    smtp_key = session.get("smtp_key")
    if smtp_key:
        with SMTP_STORE_LOCK:
            SMTP_SESSION_STORE[smtp_key] = updated
    return updated


def _get_valid_access_token(auth_session: dict) -> str | None:
    if auth_session["expires_at"] - time.time() > 60:
        return auth_session["access_token"]
    updated = _refresh_access_token(auth_session)
    if not updated:
        return None
    return updated["access_token"]


def _tokenize(text: str) -> list[str]:
    return [w.strip(".,!?:;()[]{}\"'").lower() for w in text.split() if w.strip()]


def _vectorize(text: str) -> Counter:
    return Counter(_tokenize(text))


def _cosine_similarity(a: Counter, b: Counter) -> float:
    shared = set(a.keys()) & set(b.keys())
    numerator = sum(a[t] * b[t] for t in shared)
    denom_a = sqrt(sum(v * v for v in a.values()))
    denom_b = sqrt(sum(v * v for v in b.values()))
    if denom_a == 0 or denom_b == 0:
        return 0.0
    return numerator / (denom_a * denom_b)


def _track_message_sent(message_id: str, sender_email: str, recipient_email: str, subject: str) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO email_events(message_id, sender_email, recipient_email, subject, sent_at, opens, last_opened_at)
            VALUES (?, ?, ?, ?, ?, 0, NULL)
            """,
            (message_id, sender_email, recipient_email, subject, int(time.time())),
        )


@app.route("/")
def index():
    return render_template("connect.html")


@app.route("/generate")
def generate_page():
    return render_template("generate.html")


@app.route("/send")
def send_page():
    return render_template("send.html")


@app.route("/schedule")
def schedule_redirect():
    return render_template("send.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/api/oauth/start")
def oauth_start():
    provider = (request.args.get("provider") or "").strip().lower()
    if provider not in OAUTH_CONFIG:
        return jsonify({"error": "Unsupported provider"}), 400

    ip = _client_ip()
    if _auth_rate_limited(ip):
        return jsonify({"error": "Too many sign-in attempts. Please wait and try again."}), 429

    cfg = OAUTH_CONFIG[provider]
    if not cfg["client_id"] or not cfg["client_secret"]:
        return jsonify({"error": f"OAuth is not configured for {provider}. Set client id/secret env vars first."}), 500

    state = token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    session["oauth_state"] = state
    session["oauth_provider"] = provider
    session["oauth_code_verifier"] = verifier

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": OAUTH_CALLBACK_URL,
        "response_type": "code",
        "scope": " ".join(cfg["scopes"]),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{cfg['auth_url']}?{urlencode(params)}")


@app.route("/api/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.pop("oauth_state", None)
    provider = session.pop("oauth_provider", None)
    verifier = session.pop("oauth_code_verifier", None)

    if not code or not state or not expected_state or state != expected_state or not provider:
        return redirect("/?auth=failed")

    cfg = OAUTH_CONFIG.get(provider)
    if not cfg or not verifier:
        return redirect("/?auth=failed")

    payload = {
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "code": code,
        "redirect_uri": OAUTH_CALLBACK_URL,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }

    response = requests.post(cfg["token_url"], data=payload, timeout=10)
    if not response.ok:
        return redirect("/?auth=failed")

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return redirect("/?auth=failed")

    email = _fetch_profile_email(provider, access_token)
    if not email:
        return redirect("/?auth=failed")

    _clear_auth_session()
    _set_auth_session(provider=provider, email=email, token_data=token_data)
    return redirect("/generate?auth=success")


@app.route("/api/linkedin/auth/start")
def linkedin_auth_start():
    if not LINKEDIN_CONFIG["client_id"] or not LINKEDIN_CONFIG["client_secret"]:
        return jsonify({"error": "LinkedIn OAuth is not configured."}), 500

    state = token_urlsafe(24)
    session["linkedin_state"] = state
    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CONFIG["client_id"],
        "redirect_uri": LINKEDIN_CALLBACK_URL,
        "state": state,
        "scope": " ".join(LINKEDIN_CONFIG["scopes"]),
    }
    return redirect(f"{LINKEDIN_CONFIG['auth_url']}?{urlencode(params)}")


@app.route("/api/linkedin/callback")
def linkedin_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.pop("linkedin_state", None)

    if not code or not state or state != expected_state:
        return redirect("/generate?linkedin=failed")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINKEDIN_CALLBACK_URL,
        "client_id": LINKEDIN_CONFIG["client_id"],
        "client_secret": LINKEDIN_CONFIG["client_secret"],
    }
    response = requests.post(LINKEDIN_CONFIG["token_url"], data=payload, timeout=10)
    if not response.ok:
        return redirect("/generate?linkedin=failed")

    token_data = response.json()
    session["linkedin_token"] = token_data.get("access_token")
    session["linkedin_connected"] = True
    return redirect("/generate?linkedin=success")


@app.route("/api/linkedin/status")
def linkedin_status():
    return jsonify({"connected": bool(session.get("linkedin_connected"))})


@app.route("/api/linkedin/post", methods=["POST"])
def linkedin_post():
    token = session.get("linkedin_token")
    if not token:
        return jsonify({"error": "LinkedIn is not connected."}), 401

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400

    # Lightweight integration endpoint: accepts request and relays to LinkedIn UGC API if configured.
    # This endpoint returns 501 if required LinkedIn member URN is not configured.
    member_urn = os.getenv("LINKEDIN_MEMBER_URN", "")
    if not member_urn:
        return jsonify({"error": "Set LINKEDIN_MEMBER_URN to publish posts."}), 501

    payload = {
        "author": member_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": message},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    response = requests.post(
        f"{LINKEDIN_CONFIG['api_base']}/ugcPosts",
        headers={"Authorization": f"Bearer {token}", "X-Restli-Protocol-Version": "2.0.0"},
        json=payload,
        timeout=10,
    )
    if not response.ok:
        return jsonify({"error": "LinkedIn API request failed.", "details": response.text[:200]}), 502
    return jsonify({"success": True})


@app.route("/api/context/index", methods=["POST"])
def context_index():
    auth_session = _get_auth_session()
    if not auth_session:
        return jsonify({"error": "Sign in first."}), 401

    data = request.get_json(silent=True) or {}
    chunks = data.get("chunks") or []
    if not isinstance(chunks, list) or not chunks:
        return jsonify({"error": "Provide a non-empty list of text chunks."}), 400

    with VECTOR_LOCK:
        VECTOR_INDEX[auth_session["email"]] = [
            {"text": chunk, "vector": _vectorize(str(chunk))}
            for chunk in chunks
            if str(chunk).strip()
        ]

    return jsonify({"success": True, "indexed": len(VECTOR_INDEX[auth_session['email']])})


@app.route("/api/context/retrieve", methods=["POST"])
def context_retrieve():
    auth_session = _get_auth_session()
    if not auth_session:
        return jsonify({"error": "Sign in first."}), 401

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    k = int(data.get("k") or 3)
    if not query:
        return jsonify({"error": "Query is required."}), 400

    with VECTOR_LOCK:
        docs = VECTOR_INDEX.get(auth_session["email"], [])

    qv = _vectorize(query)
    scored = []
    for doc in docs:
        score = _cosine_similarity(qv, doc["vector"])
        scored.append({"text": doc["text"], "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)

    return jsonify({"results": scored[: max(1, min(k, 10))]})


@app.route("/track/open/<message_id>.png")
def track_open(message_id: str):
    now = int(time.time())
    with _db_conn() as conn:
        conn.execute(
            """
            UPDATE email_events
            SET opens = opens + 1, last_opened_at = ?
            WHERE message_id = ?
            """,
            (now, message_id),
        )
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yXJ0AAAAASUVORK5CYII=")
    return Response(pixel, mimetype="image/png")


@app.route("/api/dashboard/open-rates")
def dashboard_open_rates():
    auth_session = _get_auth_session()
    if not auth_session:
        return jsonify({"error": "Sign in first."}), 401

    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT message_id, recipient_email, subject, sent_at, opens, last_opened_at
            FROM email_events
            WHERE sender_email = ?
            ORDER BY sent_at DESC
            LIMIT 200
            """,
            (auth_session["email"],),
        ).fetchall()

    sent_count = len(rows)
    opened_count = sum(1 for row in rows if row["opens"] > 0)
    open_rate = round((opened_count / sent_count * 100), 2) if sent_count else 0

    items = [
        {
            "message_id": row["message_id"],
            "recipient_email": row["recipient_email"],
            "subject": row["subject"],
            "sent_at": row["sent_at"],
            "opens": row["opens"],
            "last_opened_at": row["last_opened_at"],
        }
        for row in rows
    ]
    return jsonify({"sent_count": sent_count, "opened_count": opened_count, "open_rate": open_rate, "items": items})


@app.route("/api/send", methods=["POST"])
def send_email():
    auth_session = _get_auth_session()
    if not auth_session:
        return jsonify({"error": "Not connected. Sign in first."}), 401

    data = request.get_json(silent=True) or {}
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()

    if not to_email or not subject or not body:
        return jsonify({"error": "Recipient, subject, and body are required"}), 400

    access_token = _get_valid_access_token(auth_session)
    if not access_token:
        _clear_auth_session()
        return jsonify({"error": "Session expired. Please sign in again."}), 401

    cfg = OAUTH_CONFIG[auth_session["provider"]]
    message_id = token_urlsafe(12)
    tracking_pixel = f'<img src="{TRACKING_BASE_URL}/track/open/{message_id}.png" width="1" height="1" alt="" style="display:none;" />'

    try:
        msg = EmailMessage()
        msg["From"] = auth_session["email"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        html_body = f"<div>{body.replace(chr(10), '<br>')}</div>{tracking_pixel}"
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            _xoauth2_login(server, auth_session["email"], access_token)
            server.send_message(msg)

        _track_message_sent(message_id, auth_session["email"], to_email, subject)
        return jsonify({"success": True, "message": f"Email sent to {to_email}!", "message_id": message_id})
    except smtplib.SMTPAuthenticationError:
        _clear_auth_session()
        return jsonify({"error": "OAuth authentication failed. Please sign in again."}), 401
    except Exception:
        return jsonify({"error": "Failed to send email. Please retry."}), 500


@app.route("/api/status")
def connection_status():
    auth_session = _get_auth_session()
    if auth_session:
        return jsonify(
            {
                "connected": True,
                "email": auth_session["email"],
                "provider": auth_session["provider"],
                "auth": "oauth2",
            }
        )
    return jsonify({"connected": False})


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )
