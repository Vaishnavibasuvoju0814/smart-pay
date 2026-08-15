"""
PaymentProcessor: the glue between the Strategy pattern (payment methods)
and the Observer pattern (notifications) -- now with the pieces a real
payment system actually needs:

  - Retries for *transient* failures only (e.g. gateway timeout), never
    for terminal failures (e.g. declined card) -- retrying a decline
    won't fix it and just wastes a gateway call.
  - Idempotency: if the same idempotency_key is submitted twice (e.g. a
    client retrying after a network blip on their end), the cached result
    is returned instead of charging the customer again.
  - Persistence: every attempt (success or failure) is recorded via a
    TransactionStore, so state survives a restart and can be queried later.

PaymentProcessor still only imports the *abstract* PaymentMethod and
PaymentObserver interfaces -- never concrete payment/notifier classes --
which is what keeps payment logic and notification logic decoupled.
"""

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from payment_methods import PaymentMethod
from notifiers import PaymentObserver
from storage import TransactionStore


@dataclass
class ProcessedPayment:
    """Result handed back to the caller of `process_payment`."""
    txn_id: str
    method: str
    amount: float
    success: bool
    message: str
    error_code: Optional[str] = None


class PaymentProcessor:
    """Subject (Observer pattern) + Context (Strategy pattern)."""

    def __init__(
        self,
        payment_method: PaymentMethod,
        store: Optional[TransactionStore] = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.2,
    ):
        self._payment_method = payment_method
        self._observers: List[PaymentObserver] = []
        self._store = store
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    # ---- Strategy side ------------------------------------------------
    def set_payment_method(self, payment_method: PaymentMethod) -> None:
        """Swap the payment strategy at runtime."""
        self._payment_method = payment_method

    # ---- Observer side --------------------------------------------------
    def attach(self, observer: PaymentObserver) -> None:
        self._observers.append(observer)

    def detach(self, observer: PaymentObserver) -> None:
        self._observers.remove(observer)

    def _notify_all(self, event: Dict[str, Any]) -> None:
        for observer in self._observers:
            observer.update(event)

    # ---- Core workflow --------------------------------------------------
    def process_payment(
        self, amount: float, idempotency_key: Optional[str] = None
    ) -> ProcessedPayment:

        # 1. Idempotency check -- avoid double-charging on a retried request.
        if idempotency_key and self._store:
            cached = self._store.find_by_idempotency_key(idempotency_key)
            if cached:
                print(
                    f"[Idempotency] Key '{idempotency_key}' already processed "
                    f"as txn {cached['txn_id']} -- returning cached result."
                )
                return ProcessedPayment(
                    txn_id=cached["txn_id"],
                    method=cached["method"],
                    amount=cached["amount"],
                    success=cached["status"] == "success",
                    message=cached["message"],
                    error_code=cached.get("error_code"),
                )

        print(f"\n--- Processing payment via {self._payment_method.name} ---")

        # 2. Attempt payment, retrying only transient failures.
        attempt = 0
        result = self._payment_method.pay(amount)
        while not result.success and result.transient and attempt < self._max_retries:
            attempt += 1
            wait = self._retry_backoff_seconds * attempt
            print(
                f"[Retry] Transient error ('{result.error_code}'). "
                f"Retrying in {wait:.1f}s (attempt {attempt}/{self._max_retries}) ..."
            )
            time.sleep(wait)
            result = self._payment_method.pay(amount)

        txn_id = str(uuid.uuid4())[:8].upper()
        processed = ProcessedPayment(
            txn_id=txn_id,
            method=self._payment_method.name,
            amount=amount,
            success=result.success,
            message=result.message,
            error_code=result.error_code,
        )

        # 3. Persist the outcome regardless of success/failure.
        if self._store:
            self._store.save(
                {
                    "txn_id": txn_id,
                    "idempotency_key": idempotency_key,
                    "amount": amount,
                    "method": self._payment_method.name,
                    "status": "success" if result.success else "failed",
                    "error_code": result.error_code,
                    "message": result.message,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

        # 4. Notify observers only on success.
        if result.success:
            event = {
                "amount": amount,
                "method": self._payment_method.name,
                "txn_id": txn_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            self._notify_all(event)
        else:
            print(f"Payment failed [{result.error_code}]: {result.message}. "
                  f"Notifications not sent.")

        return processed
