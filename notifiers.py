"""
Observer Pattern implementation for payment notifications.

Every notifier implements the same `PaymentObserver` interface. The
PaymentProcessor (the "subject") calls `update()` on each attached observer
whenever a payment succeeds, without knowing anything about how a specific
channel actually delivers the notification.

EmailNotifier sends a REAL email via SMTP when credentials are configured
(see README "Sending real emails" section). SMSNotifier and PushNotifier
still print to console -- real SMS/push require a paid third-party account
(Twilio, FCM); say the word if you want either wired up for real too.
"""

import os
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any, Dict


class PaymentObserver(ABC):
    """Observer interface - anything that wants to react to payment events."""

    @abstractmethod
    def update(self, event: Dict[str, Any]) -> None:
        raise NotImplementedError


class EmailNotifier(PaymentObserver):
    """
    Sends a real email via SMTP when these environment variables are set:

        SMTP_HOST      (default: smtp.gmail.com)
        SMTP_PORT      (default: 465)
        SMTP_USER      the sending account, e.g. yourname@gmail.com
        SMTP_PASSWORD  a 16-character Gmail "App Password" -- NOT your
                       normal Google account password

    If SMTP_USER / SMTP_PASSWORD aren't set, falls back to printing to the
    console (clearly labeled SIMULATED) so the rest of the demo still runs
    without requiring an email account to be configured.
    """

    def __init__(self, to_email: str):
        self.to_email = to_email
        self.smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "465"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_password = os.environ.get("SMTP_PASSWORD")

    def update(self, event: Dict[str, Any]) -> None:
        subject = f"Payment Confirmation - Rs.{event['amount']:.2f}"
        body = (
            f"Your payment of Rs.{event['amount']:.2f} via {event['method']} "
            f"was successful.\n\n"
            f"Transaction ID: {event['txn_id']}\n"
            f"Time: {event['timestamp']}\n\n"
            f"-- Smart Pay"
        )

        if not self.smtp_user or not self.smtp_password:
            print(
                f"[Email -> {self.to_email}] (SIMULATED - set SMTP_USER / "
                f"SMTP_PASSWORD env vars to send for real) {subject}"
            )
            return

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.to_email
        msg.set_content(body)

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            print(f"[Email -> {self.to_email}] Real email sent successfully.")
        except Exception as exc:
            print(f"[Email -> {self.to_email}] FAILED to send real email: {exc}")


class SMSNotifier(PaymentObserver):
    """
    Simulated for now -- real SMS needs a paid account with a provider
    like Twilio. Ask if you want this wired up for real (takes ~10 lines
    once you have a Twilio account SID/auth token/from-number).
    """

    def __init__(self, phone: str):
        self.phone = phone

    def update(self, event: Dict[str, Any]) -> None:
        print(
            f"[SMS -> {self.phone}] (SIMULATED) Rs.{event['amount']:.2f} paid via "
            f"{event['method']}. Txn: {event['txn_id']}"
        )


class PushNotifier(PaymentObserver):
    """Simulated -- real push needs a mobile app + FCM/APNs setup."""

    def __init__(self, device_id: str):
        self.device_id = device_id

    def update(self, event: Dict[str, Any]) -> None:
        print(
            f"[Push -> device {self.device_id}] (SIMULATED) Payment successful: "
            f"Rs.{event['amount']:.2f} via {event['method']}"
        )
