"""Step 7: send the email - only ever to TO_ADDRESS (your own inbox), never to the prospect.

Senders, in order: Resend (RESEND_API_KEY), then Gmail (GMAIL_APP_PASSWORD). With neither, the email is
written to outbox/ so you can still see exactly what would have gone out.
"""
import os
import re
import smtplib
from email.message import EmailMessage

import requests

import config


def _compose(domain, contact, subject, body):
    subj = f"[Sprinto draft for {contact['name']}, {domain}] {subject}"
    note = f"(Would go to: {contact['name']} <{contact.get('email') or 'email not found'}>, {contact['title']})\n\n"
    return subj, note + body


def _via_resend(subj, text):
    r = requests.post("https://api.resend.com/emails", timeout=30,
                      headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                      json={"from": config.RESEND_FROM, "to": [config.TO_ADDRESS], "subject": subj, "text": text})
    if r.status_code >= 300:
        raise RuntimeError(f"Resend HTTP {r.status_code}: {r.text[:200]}")
    return f"sent to {config.TO_ADDRESS} via Resend (id {r.json().get('id')})"


def _via_gmail(subj, text):
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subj, config.GMAIL_ADDRESS, config.TO_ADDRESS
    msg.set_content(text)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        s.send_message(msg)
    return f"sent to {config.TO_ADDRESS} via Gmail"


def send(domain, contact, subject, body):
    if not config.TO_ADDRESS:
        raise RuntimeError("TO_ADDRESS is not set in .env; refusing to send anywhere.")
    subj, text = _compose(domain, contact, subject, body)  # the prospect's address is never a recipient
    if config.RESEND_API_KEY:
        return _via_resend(subj, text)
    if config.GMAIL_APP_PASSWORD:
        return _via_gmail(subj, text)

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subj, config.TO_ADDRESS, config.TO_ADDRESS
    msg.set_content(text)
    os.makedirs("outbox", exist_ok=True)
    path = os.path.join("outbox", re.sub(r"[^a-z0-9.-]", "_", domain.lower()) + ".eml")
    with open(path, "wb") as f:
        f.write(bytes(msg))
    return f"no Resend key or Gmail app password: saved to {path}"
