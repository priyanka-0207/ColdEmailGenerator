import app as flask_app


def _configure_oauth_for_tests():
    flask_app.OAUTH_CONFIG["gmail"]["client_id"] = "test-google-client"
    flask_app.OAUTH_CONFIG["gmail"]["client_secret"] = "test-google-secret"
    flask_app.OAUTH_CONFIG["outlook"]["client_id"] = "test-ms-client"
    flask_app.OAUTH_CONFIG["outlook"]["client_secret"] = "test-ms-secret"


class FakeResponse:
    def __init__(self, payload, ok=True, text=""):
        self._payload = payload
        self.ok = ok
        self.text = text

    def json(self):
        return self._payload


class FakeSMTP:
    def __init__(self, *_args, **_kwargs):
        self.sent = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        return None

    def docmd(self, _cmd, _args):
        return 235, b"2.7.0 Accepted"

    def send_message(self, _msg):
        self.sent = True


def _authenticate_test_client(client, key="key1", email="user@example.com"):
    with client.session_transaction() as sess:
        sess["smtp_key"] = key

    flask_app.SMTP_SESSION_STORE[key] = {
        "provider": "gmail",
        "email": email,
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": 9999999999,
    }


def test_oauth_start_sets_state_and_redirects():
    _configure_oauth_for_tests()
    flask_app.AUTH_ATTEMPTS.clear()
    client = flask_app.app.test_client()

    response = client.get("/api/oauth/start?provider=gmail")

    assert response.status_code == 302
    assert "accounts.google.com" in response.location
    with client.session_transaction() as sess:
        assert "oauth_state" in sess
        assert sess["oauth_provider"] == "gmail"
        assert "oauth_code_verifier" in sess


def test_oauth_callback_persists_server_side_session(monkeypatch):
    _configure_oauth_for_tests()

    def fake_post(*_args, **_kwargs):
        return FakeResponse({"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})

    def fake_get(*_args, **_kwargs):
        return FakeResponse({"email": "user@example.com"})

    monkeypatch.setattr(flask_app.requests, "post", fake_post)
    monkeypatch.setattr(flask_app.requests, "get", fake_get)

    client = flask_app.app.test_client()
    with client.session_transaction() as sess:
        sess["oauth_state"] = "abc"
        sess["oauth_provider"] = "gmail"
        sess["oauth_code_verifier"] = "verifier"

    response = client.get("/api/oauth/callback?code=123&state=abc")

    assert response.status_code == 302
    assert response.location.endswith("/generate?auth=success")
    with client.session_transaction() as sess:
        assert "smtp_key" in sess


def test_send_uses_oauth_authenticated_smtp(monkeypatch):
    _configure_oauth_for_tests()
    monkeypatch.setattr(flask_app.smtplib, "SMTP", FakeSMTP)

    client = flask_app.app.test_client()
    _authenticate_test_client(client)

    response = client.post("/api/send", json={"to_email": "to@example.com", "subject": "Hey", "body": "Body"})

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json.get("message_id")


def test_vector_context_index_and_retrieve():
    client = flask_app.app.test_client()
    _authenticate_test_client(client, key="vec1", email="vec@example.com")

    idx = client.post(
        "/api/context/index",
        json={"chunks": ["Built Python automation for SDR outreach", "Managed CRM and email experiments"]},
    )
    assert idx.status_code == 200
    assert idx.json["indexed"] == 2

    res = client.post("/api/context/retrieve", json={"query": "python outreach automation", "k": 1})
    assert res.status_code == 200
    assert len(res.json["results"]) == 1
    assert "Python automation" in res.json["results"][0]["text"]


def test_dashboard_open_rates_returns_metrics():
    client = flask_app.app.test_client()
    _authenticate_test_client(client, key="dash1", email="dash@example.com")

    flask_app._track_message_sent("msg-1", "dash@example.com", "a@b.com", "Subject A")
    with flask_app._db_conn() as conn:
        conn.execute("UPDATE email_events SET opens = 1, last_opened_at = ? WHERE message_id = ?", (123456, "msg-1"))

    response = client.get("/api/dashboard/open-rates")
    assert response.status_code == 200
    assert response.json["sent_count"] >= 1
    assert response.json["opened_count"] >= 1
