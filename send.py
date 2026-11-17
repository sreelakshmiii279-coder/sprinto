"""Step 7: send the email - only ever to TO_ADDRESS (your own inbox), never to the prospect.

With a Gmail app password in .env it sends through Gmail; without one it writes the email to outbox/
so you can still see exactly what would have gone out.
"""
import os
import re
import smtplib
from email.message import EmailMessage

import config


def send(domain, contact, subject, body):
    if not config.TO_ADDRESS:
        raise RuntimeError("TO_ADDRESS is not set in .env; refusing to send anywhere.")
    msg = EmailMessage()
    msg["Subject"] = f"[Sprinto draft for {contact['name']}, {domain}] {subject}"
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = config.TO_ADDRESS  # hardcoded recipient: the prospect's address is never used
    note = f"(Would go to: {contact['name']} <{contact.get('email') or 'email not found'}>, {contact['title']})\n\n"
    msg.set_content(note + body)

    if config.GMAIL_APP_PASSWORD:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            s.send_message(msg)
        return f"sent to {config.TO_ADDRESS}"

    os.makedirs("outbox", exist_ok=True)
    path = os.path.join("outbox", re.sub(r"[^a-z0-9.-]", "_", domain.lower()) + ".eml")
    with open(path, "wb") as f:
        f.write(bytes(msg))
    return f"no Gmail app password: saved to {path}"
