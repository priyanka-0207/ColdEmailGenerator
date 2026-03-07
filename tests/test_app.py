from generator import generate_cold_email


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
