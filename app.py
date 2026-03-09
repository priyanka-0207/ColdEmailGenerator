import os
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")

SMTP_CONFIG = {
    "gmail": {"server": "smtp.gmail.com", "port": 587},
    "outlook": {"server": "smtp.office365.com", "port": 587},
}


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


@app.route("/api/connect", methods=["POST"])
def connect():
    """Test SMTP connection and save to session."""
    data = request.get_json()
    provider = (data.get("provider") or "gmail").strip().lower()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and app password are required"}), 400

    if provider not in SMTP_CONFIG:
        return jsonify({"error": "Unsupported provider"}), 400

    cfg = SMTP_CONFIG[provider]

    try:
        print(f"[DEBUG] Connecting to {cfg['server']}:{cfg['port']}...")
        with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as server:
            server.starttls()
            server.login(email, password)
        print(f"[DEBUG] Connected successfully as {email}")

        session["smtp"] = {
            "provider": provider,
            "email": email,
            "password": password,
        }
        return jsonify({"success": True, "message": f"Connected as {email}"})

    except smtplib.SMTPAuthenticationError as e:
        print(f"[DEBUG] Auth error: {e}")
        return jsonify({"error": "Authentication failed. Make sure you're using a Gmail App Password, not your regular password."}), 401
    except Exception as e:
        print(f"[DEBUG] Connection error: {e}")
        return jsonify({"error": f"Connection failed: {str(e)}"}), 500


@app.route("/api/send", methods=["POST"])
def send_email():
    """Send email via SMTP."""
    smtp = session.get("smtp")
    if not smtp:
        return jsonify({"error": "Not connected. Go back and connect your email first."}), 401

    data = request.get_json()
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()

    if not to_email or not subject or not body:
        return jsonify({"error": "Recipient, subject, and body are required"}), 400

    cfg = SMTP_CONFIG[smtp["provider"]]

    try:
        msg = EmailMessage()
        msg["From"] = smtp["email"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        print(f"[DEBUG] Sending email to {to_email}...")
        with smtplib.SMTP(cfg["server"], cfg["port"], timeout=15) as server:
            server.starttls()
            server.login(smtp["email"], smtp["password"])
            server.send_message(msg)
        print(f"[DEBUG] Email sent successfully!")

        return jsonify({"success": True, "message": f"Email sent to {to_email}!"})

    except smtplib.SMTPAuthenticationError:
        return jsonify({"error": "Authentication failed. Reconnect with a valid app password."}), 401
    except Exception as e:
        print(f"[DEBUG] Send error: {e}")
        return jsonify({"error": f"Failed to send: {str(e)}"}), 500


@app.route("/api/status")
def connection_status():
    """Check if user is connected."""
    smtp = session.get("smtp")
    if smtp:
        return jsonify({"connected": True, "email": smtp["email"], "provider": smtp["provider"]})
    return jsonify({"connected": False})


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )