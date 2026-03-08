def generate_cold_email(
    resume_context: str,
    target_company: str,
    target_role: str,
    recipient_name: str,
    tone: str,
    sender_name: str = "",
) -> tuple[str, str]:
    highlights = [line.strip(" -•") for line in resume_context.splitlines() if line.strip()]
    highlights = highlights[:3]
    bullets = "\n".join(f"- {item}" for item in highlights)

    intro = f"Hi {recipient_name}," if recipient_name else "Hi there,"
    tone_line = {
        "confident": "I wanted to reach out directly because I believe I can create immediate impact.",
        "friendly": "I hope your week is going well — I wanted to say hello and introduce myself.",
        "direct": "I am writing to express my interest and ask for a short conversation.",
    }.get(tone, "I wanted to introduce myself and briefly share why I'm reaching out.")

    sign_off = sender_name if sender_name else "[Your Name]"

    subject = f"Interested in {target_role} opportunities at {target_company}".strip()
    bullet_text = bullets or '- Strong communication and ownership\n- Proven problem-solving'
    body = (
        f"{intro}\n\n"
        f"{tone_line}\n\n"
        f"I'm interested in {target_role} opportunities at {target_company}. Based on my background, I can contribute in these ways:\n"
        f"{bullet_text}\n\n"
        "If you are open to it, I'd value 10-15 minutes to learn about your team's needs and share how I can help.\n\n"
        "Best regards,\n"
        f"{sign_off}"
    )
    return subject, body