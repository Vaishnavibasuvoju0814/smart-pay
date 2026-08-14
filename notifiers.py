"""
Observer Pattern implementation for payment notifications.

Every notifier implements the same `PaymentObserver` interface. The
PaymentProcessor (the "subject") calls `update()` on each attached observer
whenever a payment succeeds, without knowing anything about how a specific
channel actually delivers the notification.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class PaymentObserver(ABC):
    """Observer interface - anything that wants to react to payment events."""

    @abstractmethod
    def update(self, event: Dict[str, Any]) -> None:
        raise NotImplementedError


class EmailNotifier(PaymentObserver):
    def __init__(self, email: str):
        self.email = email

    def update(self, event: Dict[str, Any]) -> None:
        print(
            f"[Email -> {self.email}] Payment of Rs.{event['amount']:.2f} "
            f"via {event['method']} succeeded. Txn ID: {event['txn_id']}"
        )


class SMSNotifier(PaymentObserver):
    def __init__(self, phone: str):
        self.phone = phone

    def update(self, event: Dict[str, Any]) -> None:
        print(
            f"[SMS -> {self.phone}] Rs.{event['amount']:.2f} paid via "
            f"{event['method']}. Txn: {event['txn_id']}"
        )


# --- Example of adding a brand new channel WITHOUT touching anything above ---
class PushNotifier(PaymentObserver):
    """Demonstrates extensibility: added later, zero changes elsewhere."""

    def __init__(self, device_id: str):
        self.device_id = device_id

    def update(self, event: Dict[str, Any]) -> None:
        print(
            f"[Push -> device {self.device_id}] Payment successful: "
            f"Rs.{event['amount']:.2f} via {event['method']}"
        )
