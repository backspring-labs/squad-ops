"""Mailing the ledger's digest."""

import smtplib
from email.message import EmailMessage


def digest(ledger):
    lines = [f"{name}: {count}" for name, count in ledger.counters().items()]
    return "\n".join(lines) or "(empty)"


def send_digest(ledger, host, recipient, port=25):
    message = EmailMessage()
    message["Subject"] = "Tally digest"
    message["From"] = "tally@localhost"
    message["To"] = recipient
    message.set_content(digest(ledger))
    with smtplib.SMTP(host, port, timeout=10) as smtp:
        smtp.send_message(message)
