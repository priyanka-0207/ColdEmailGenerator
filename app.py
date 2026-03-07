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

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scheduler.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


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
        guide_url="https://support.microsoft.com/en-us/account-billing/how-to-get-and-use-app-passwords-5896ed9b-4263-e681-128a-a6f2979a7944",
    ),
}

_scheduler_started = False


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
            SELECT id, provider, sender_email, recipient_email, subject, send_at_utc, status, error_message
            FROM scheduled_emails
            ORDER BY datetime(send_at_utc) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def send_email(provider: str, sender_email: str, sender_password: str, recipient_email: str, subject: str, body: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError("Unsupported provider")

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
                    except Exception as exc:  # noqa: BLE001
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


@app.route("/healthz", methods=["GET"])
def healthz():
    return {"status": "ok"}, 200

@app.route("/", methods=["GET"])
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
    provider = request.form.get("provider", "").lower()
    sender_email = request.form.get("sender_email", "").strip()
    sender_password = request.form.get("sender_password", "").strip()

    if provider not in PROVIDERS or not sender_email or not sender_password:
        flash("Please choose Gmail/Outlook and provide sender email + app password.", "error")
        return redirect(url_for("connect_page"))

    session["connection"] = {
        "provider": provider,
        "sender_email": sender_email,
        "sender_password": sender_password,
    }
    flash(f"Connected {provider.title()} account for scheduling.", "success")
    return redirect(url_for("generate_page"))


@app.route("/generate", methods=["GET"])
def generate_page():
    return render_template(
        "generate.html",
        current_step="generate",
        generated_subject=session.get("generated_subject", ""),
        generated_body=session.get("generated_body", ""),
    )


@app.route("/generate", methods=["POST"])
def generate():
    resume_context = request.form.get("resume_context", "")
    target_company = request.form.get("target_company", "")
    target_role = request.form.get("target_role", "")
    recipient_name = request.form.get("recipient_name", "")
    tone = request.form.get("tone", "friendly")

    subject, body = generate_cold_email(
        resume_context=resume_context,
        target_company=target_company or "the company",
        target_role=target_role or "relevant",
        recipient_name=recipient_name,
        tone=tone,
    )

    session["generated_subject"] = subject
    session["generated_body"] = body
    flash("Draft generated. Review and schedule it on the next page.", "success")
    return redirect(url_for("schedule_page"))


@app.route("/schedule", methods=["GET"])
def schedule_page():
    return render_template(
        "schedule.html",
        current_step="schedule",
        generated_subject=session.get("generated_subject", ""),
        generated_body=session.get("generated_body", ""),
        jobs=fetch_recent_jobs(),
    )


@app.route("/schedule", methods=["POST"])
def schedule():
    connection = session.get("connection")
    if not connection:
        flash("Connect Gmail or Outlook first.", "error")
        return redirect(url_for("connect_page"))

    recipient_email = request.form.get("recipient_email", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    send_at_local = request.form.get("send_at", "").strip()

    if not recipient_email or not subject or not body or not send_at_local:
        flash("Fill recipient, subject, body, and schedule time.", "error")
        return redirect(url_for("schedule_page"))

    try:
        send_at = datetime.fromisoformat(send_at_local)
        send_at_utc = send_at.astimezone(timezone.utc)
    except ValueError:
        flash("Invalid schedule date/time.", "error")
        return redirect(url_for("schedule_page"))

    with closing(get_db()) as conn:
        conn.execute(
            """
            INSERT INTO scheduled_emails (
                provider, sender_email, sender_password, recipient_email, subject, body,
                send_at_utc, status, created_at_utc
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

    flash("Email scheduled successfully.", "success")
    return redirect(url_for("schedule_page"))


start_background_services()


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )
