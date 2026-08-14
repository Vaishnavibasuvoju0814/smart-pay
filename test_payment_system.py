"""
Unit tests for the payment processing system.

Run with:  python -m unittest test_payment_system.py -v
"""

import unittest
from typing import Any, Dict, List

from payment_methods import PaymentMethod, PaymentMethodRegistry
from notifiers import PaymentObserver
from payment_processor import PaymentProcessor


class FakeSuccessPayment(PaymentMethod):
    """Test double: always succeeds."""

    @property
    def name(self) -> str:
        return "Fake Success"

    def pay(self, amount: float) -> bool:
        return True


class FakeFailurePayment(PaymentMethod):
    """Test double: always fails."""

    @property
    def name(self) -> str:
        return "Fake Failure"

    def pay(self, amount: float) -> bool:
        return False


class RecordingObserver(PaymentObserver):
    """Test double that records every event it receives."""

    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def update(self, event: Dict[str, Any]) -> None:
        self.events.append(event)


class TestPaymentMethods(unittest.TestCase):
    def test_registry_creates_known_methods(self):
        for key in ("credit_card", "upi", "net_banking", "wallet"):
            self.assertIn(key, PaymentMethodRegistry.available_methods())

    def test_registry_raises_for_unknown_method(self):
        with self.assertRaises(ValueError):
            PaymentMethodRegistry.create("bitcoin")

    def test_credit_card_pay_succeeds(self):
        card = PaymentMethodRegistry.create(
            "credit_card", card_number="4111111111111234", cvv="123"
        )
        self.assertTrue(card.pay(100.0))
        self.assertEqual(card.name, "Credit Card")


class TestPaymentProcessor(unittest.TestCase):
    def test_successful_payment_notifies_all_observers(self):
        processor = PaymentProcessor(FakeSuccessPayment())
        obs1, obs2 = RecordingObserver(), RecordingObserver()
        processor.attach(obs1)
        processor.attach(obs2)

        result = processor.process_payment(100.0)

        self.assertTrue(result)
        self.assertEqual(len(obs1.events), 1)
        self.assertEqual(len(obs2.events), 1)
        self.assertEqual(obs1.events[0]["amount"], 100.0)
        self.assertEqual(obs1.events[0]["method"], "Fake Success")
        self.assertIn("txn_id", obs1.events[0])

    def test_failed_payment_does_not_notify_observers(self):
        processor = PaymentProcessor(FakeFailurePayment())
        obs = RecordingObserver()
        processor.attach(obs)

        result = processor.process_payment(100.0)

        self.assertFalse(result)
        self.assertEqual(len(obs.events), 0)

    def test_detach_stops_further_notifications(self):
        processor = PaymentProcessor(FakeSuccessPayment())
        obs = RecordingObserver()
        processor.attach(obs)
        processor.detach(obs)

        processor.process_payment(50.0)

        self.assertEqual(len(obs.events), 0)

    def test_switching_strategy_at_runtime(self):
        processor = PaymentProcessor(FakeSuccessPayment())
        obs = RecordingObserver()
        processor.attach(obs)

        processor.process_payment(10.0)
        processor.set_payment_method(FakeFailurePayment())
        processor.process_payment(20.0)

        # Only the first (successful) payment should have notified.
        self.assertEqual(len(obs.events), 1)
        self.assertEqual(obs.events[0]["method"], "Fake Success")


if __name__ == "__main__":
    unittest.main()
