"""
PaymentProcessor: the glue between the Strategy pattern (payment methods)
and the Observer pattern (notifications).

It holds:
  - a single PaymentMethod (the current "strategy"), swappable at runtime
  - a list of PaymentObservers (the "subscribers") to notify on success

Crucially, PaymentProcessor never imports or references any *concrete*
payment method or notifier class -- only the abstract interfaces. That is
what keeps payment logic and notification logic fully decoupled and lets
both sides evolve independently.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any

from payment_methods import PaymentMethod
from notifiers import PaymentObserver


class PaymentProcessor:
    """Subject (Observer pattern) + Context (Strategy pattern)."""

    def __init__(self, payment_method: PaymentMethod):
        self._payment_method = payment_method
        self._observers: List[PaymentObserver] = []

    # ---- Strategy side --------------------------------------------------
    def set_payment_method(self, payment_method: PaymentMethod) -> None:
        """Swap the payment strategy at runtime."""
        self._payment_method = payment_method

    # ---- Observer side ----------------------------------------------------
    def attach(self, observer: PaymentObserver) -> None:
        self._observers.append(observer)

    def detach(self, observer: PaymentObserver) -> None:
        self._observers.remove(observer)

    def _notify_all(self, event: Dict[str, Any]) -> None:
        for observer in self._observers:
            observer.update(event)

    # ---- Core workflow ----------------------------------------------------
    def process_payment(self, amount: float) -> bool:
        print(f"\n--- Processing payment via {self._payment_method.name} ---")
        success = self._payment_method.pay(amount)

        if success:
            event = {
                "amount": amount,
                "method": self._payment_method.name,
                "txn_id": str(uuid.uuid4())[:8].upper(),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            self._notify_all(event)
        else:
            print("Payment failed. Notifications not sent.")

        return success
