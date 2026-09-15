"""Sends the 'proposal ready' notification email via the Gmail API.

Sends as the authenticated Google account (julienne@myadventuregroup.com.au —
the same account whose refresh token this project reuses). The reused token was
already consented for gmail.send, so no extra OAuth is needed.
"""

import base64
from email.mime.text import MIMEText


def send_email(gmail, to: str, subject: str, body_text: str) -> dict:
    """Sends a plain-text email. Returns {message_id, thread_id, to}."""
    message = MIMEText(body_text)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    sent = (
        gmail.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    return {"message_id": sent.get("id"), "thread_id": sent.get("threadId"), "to": to}
