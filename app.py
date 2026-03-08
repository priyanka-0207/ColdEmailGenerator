"""
Cold Email Generator & Scheduler
─────────────────────────────────
Multi-page wizard: Connect → Generate → Schedule
Supports Gmail and Outlook via SMTP.

Usage:
    python app.py
    Visit http://localhost:5000
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
import smtplib

from flask import Flask, flash, redirect, render_template, request, session, url_for
from generator import generate_cold_email


# ─── Config " "─────

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scheduler.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
)


# ─── Email Providers 

@dataclass
class ProviderConfig:
    smtp_server: str
    smtp_port: int
    guide_url: str


PROVIDERS = {
    "gmail": ProviderConfig(
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        guide_url="https://support.google.com/accounts/answer/185833",
    ),
    "outlook": ProviderConfig(
        smtp_server="smtp.office365.com",
        smtp_port=587,
        guide_url="https://support.microsoft.com/en-us/account-billing/"
                   "how-to-get-and-use-app-passwords-5896ed9b-4263-e681-128a-a6f2979a7944",
    ),
}


#Database

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(get_db()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                sender_password TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                send_at_utc TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'scheduled',
                error_message TEXT,
                created_at_utc TEXT NOT NULL
            )
            """
        )
        conn.commit()


def fetch_recent_jobs(limit: int = 15) -> list[sqlite3.Row]:
    with closing(get_db()) as conn:
        return conn.execute(
            """
            SELECT id, provider, sender_email, recipient_email,
                   subject, send_at_utc, status, error_message
            FROM scheduled_emails
            ORDER BY datetime(send_at_utc) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


# Email Sending 

def send_email(
    provider: str,
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    config = PROVIDERS[provider]
    message = EmailMessage()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=30) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)


#Background Scheduler 

_scheduler_started = False


def scheduler_loop() -> None:
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            with closing(get_db()) as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM scheduled_emails
                    WHERE status = 'scheduled' AND send_at_utc <= ?
                    ORDER BY send_at_utc ASC
                    """,
                    (now,),
                ).fetchall()

                for row in rows:
                    try:
                        send_email(
                            row["provider"],
                            row["sender_email"],
                            row["sender_password"],
                            row["recipient_email"],
                            row["subject"],
                            row["body"],
                        )
                        conn.execute(
                            "UPDATE scheduled_emails SET status = 'sent', error_message = NULL WHERE id = ?",
                            (row["id"],),
                        )
                    except Exception as exc:
                        conn.execute(
                            "UPDATE scheduled_emails SET status = 'failed', error_message = ? WHERE id = ?",
                            (str(exc), row["id"]),
                        )
                conn.commit()
        except Exception:
            pass

        time.sleep(30)


def start_background_services() -> None:
    global _scheduler_started
    if _scheduler_started:
        return

    init_db()
    if os.getenv("RUN_SCHEDULER", "true").lower() == "true":
        thread = threading.Thread(target=scheduler_loop, daemon=True)
        thread.start()
    _scheduler_started = True


@app.before_request
def ensure_services_started() -> None:
    start_background_services()


# Helper: Check Connection 

def require_connection():
    """Returns connection dict or None. Flashes error if missing."""
    connection = session.get("connection")
    if not connection:
        flash("Connect your email account first.", "error")
    return connection


# Routes: Step 1 — Connect 

@app.route("/")
def index():
    return redirect(url_for("connect_page"))


@app.route("/connect", methods=["GET"])
def connect_page():
    connection = session.get("connection")
    return render_template(
        "connect.html",
        providers=PROVIDERS,
        current_step="connect",
        connection=connection,
    )


@app.route("/connect", methods=["POST"])
def connect_account():
    provider = request.form.get("provider", "").strip().lower()
    sender_email = request.form.get("sender_email", "").strip()
    sender_password = request.form.get("sender_password", "").strip()

    if provider not in PROVIDERS:
        flash("Please choose Gmail or Outlook.", "error")
        return redirect(url_for("connect_page"))

    if not sender_email or not sender_password:
        flash("Please provide your email and app password.", "error")
        return redirect(url_for("connect_page"))

    # Store connection in session
    session["connection"] = {
        "provider": provider,
        "sender_email": sender_email,
        "sender_password": sender_password,
    }
    flash(f"Connected {provider.title()} account successfully.", "success")
    return redirect(url_for("generate_page"))


@app.route("/disconnect", methods=["POST"])
def disconnect_account():
    session.pop("connection", None)
    flash("Email account disconnected.", "info")
    return redirect(url_for("connect_page"))


#Routes: Step 2 — Generate

@app.route("/generate", methods=["GET"])
def generate_page():
    if not require_connection():
        return redirect(url_for("connect_page"))

    return render_template(
        "generate.html",
        current_step="generate",
        generated_subject=session.get("generated_subject", ""),
        generated_body=session.get("generated_body", ""),
    )


@app.route("/generate", methods=["POST"])
def generate():
    if not require_connection():
        return redirect(url_for("connect_page"))

    resume_context = request.form.get("resume_context", "").strip()
    target_company = request.form.get("target_company", "").strip()
    target_role = request.form.get("target_role", "").strip()
    recipient_name = request.form.get("recipient_name", "").strip()
    tone = request.form.get("tone", "friendly").strip()

    if not resume_context:
        flash("Please provide some context about yourself.", "error")
        return redirect(url_for("generate_page"))

    try:
        subject, body = generate_cold_email(
            resume_context=resume_context,
            target_company=target_company or "the company",
            target_role=target_role or "relevant",
            recipient_name=recipient_name,
            tone=tone,
        )

        session["generated_subject"] = subject
        session["generated_body"] = body
        flash("Draft generated! Review and edit below, then schedule.", "success")
        return redirect(url_for("schedule_page"))

    except Exception as exc:
        flash(f"Generation failed: {exc}", "error")
        return redirect(url_for("generate_page"))


# Routes: Step 3 — Schedule

@app.route("/schedule", methods=["GET"])
def schedule_page():
    if not require_connection():
        return redirect(url_for("connect_page"))

    return render_template(
        "schedule.html",
        current_step="schedule",
        generated_subject=session.get("generated_subject", ""),
        generated_body=session.get("generated_body", ""),
        jobs=fetch_recent_jobs(),
    )


@app.route("/schedule", methods=["POST"])
def schedule():
    connection = require_connection()
    if not connection:
        return redirect(url_for("connect_page"))

    recipient_email = request.form.get("recipient_email", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    send_at_local = request.form.get("send_at", "").strip()

    # Validation
    if not all([recipient_email, subject, body, send_at_local]):
        flash("Please fill in recipient, subject, body, and schedule time.", "error")
        return redirect(url_for("schedule_page"))

    try:
        send_at = datetime.fromisoformat(send_at_local)
        send_at_utc = send_at.astimezone(timezone.utc)
    except ValueError:
        flash("Invalid date/time format.", "error")
        return redirect(url_for("schedule_page"))

    # Don't allow scheduling in the past
    if send_at_utc < datetime.now(timezone.utc):
        flash("Cannot schedule emails in the past.", "error")
        return redirect(url_for("schedule_page"))

    # Save to database
    with closing(get_db()) as conn:
        conn.execute(
            """
            INSERT INTO scheduled_emails (
                provider, sender_email, sender_password, recipient_email,
                subject, body, send_at_utc, status, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)
            """,
            (
                connection["provider"],
                connection["sender_email"],
                connection["sender_password"],
                recipient_email,
                subject,
                body,
                send_at_utc.isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

    # Clear generated draft from session
    session.pop("generated_subject", None)
    session.pop("generated_body", None)

    flash("Email scheduled successfully!", "success")
    return redirect(url_for("schedule_page"))


#Routes: Job Management

@app.route("/cancel/<int:job_id>", methods=["POST"])
def cancel_job(job_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "UPDATE scheduled_emails SET status = 'cancelled' WHERE id = ? AND status = 'scheduled'",
            (job_id,),
        )
        conn.commit()
    flash("Scheduled email cancelled.", "info")
    return redirect(url_for("schedule_page"))


#Entry Point

if __name__ == "__main__":
    start_background_services()
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )