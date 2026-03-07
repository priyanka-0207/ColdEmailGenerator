from generator import generate_cold_email
from app import app


def test_generate_cold_email_contains_target():
    subject, body = generate_cold_email(
        resume_context="Increased reply rates by 30%\nBuilt automation scripts",
        target_company="Acme",
        target_role="SDR",
        recipient_name="Jordan",
        tone="friendly",
    )

    assert "Acme" in subject
    assert "SDR" in subject
    assert "Hi Jordan" in body
    assert "Increased reply rates by 30%" in body


def test_connect_redirects_to_generate_when_form_is_valid():
    client = app.test_client()

    response = client.post(
        "/connect",
        data={
            "provider": "gmail",
            "sender_email": "user@example.com",
            "sender_password": "app-pass",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/generate?connected=1")


def test_generate_page_shows_connected_notice_after_redirect():
    client = app.test_client()
    with client.session_transaction() as session_data:
        session_data["connection"] = {
            "provider": "outlook",
            "sender_email": "user@example.com",
            "sender_password": "app-pass",
        }

    response = client.get("/generate?connected=1")

    assert response.status_code == 200
    assert b"Connected Outlook" in response.data
