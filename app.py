import os
import resend
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-change-me")

# Initialize Resend with API key
resend.api_key = os.getenv("RESEND_API_KEY")


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
    """Save sender email to session (no SMTP verification needed with Resend)."""
    data = request.get_json()
    email = (data.get("email") or "").strip()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # With Resend, we don't need password - just save the sender email
    # Note: The "from" email must be verified in your Resend dashboard,
    # OR use Resend's default: "onboarding@resend.dev" for testing
    session["sender"] = {"email": email}
    
    return jsonify({"success": True, "message": f"Connected as {email}"})


@app.route("/api/send", methods=["POST"])
def send_email():
    """Send email via Resend API."""
    sender = session.get("sender")
    if not sender:
        return jsonify({"error": "Not connected. Go back and connect your email first."}), 401

    if not resend.api_key:
        return jsonify({"error": "RESEND_API_KEY not configured on server"}), 500

    data = request.get_json()
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()

    if not to_email or not subject or not body:
        return jsonify({"error": "Recipient, subject, and body are required"}), 400

    try:
        # For testing, use Resend's default sender
        # For production, verify your domain in Resend dashboard
        from_email = f"ColdMail <onboarding@resend.dev>"
        
        # If you've verified your domain, use:
        # from_email = f"ColdMail <{sender['email']}>"

        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "text": body,
            # Optional: add HTML version
            # "html": f"<p>{body}</p>",
        }

        email_response = resend.Emails.send(params)
        
        return jsonify({
            "success": True, 
            "message": f"Email sent to {to_email}!",
            "id": email_response.get("id")
        })

    except resend.exceptions.ResendError as e:
        return jsonify({"error": f"Resend error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to send: {str(e)}"}), 500


@app.route("/api/status")
def connection_status():
    """Check if user is connected."""
    sender = session.get("sender")
    if sender:
        return jsonify({"connected": True, "email": sender["email"]})
    return jsonify({"connected": False})


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
    )