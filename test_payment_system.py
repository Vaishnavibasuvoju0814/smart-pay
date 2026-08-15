"""
Unit tests for the payment processing system.

Run with:  python -m unittest test_payment_system.py -v
"""

import os
import tempfile
import unittest
from typing import Any, Dict, List

from payment_methods import PaymentMethod, PaymentMethodRegistry, PaymentResult
from notifiers import PaymentObserver
from payment_processor import PaymentProcessor
from storage import TransactionStore


class FakeSuccessPayment(PaymentMethod):
    """Test double: always succeeds."""

    @property
    def name(self) -> str:
        return "Fake Success"

    def pay(self, amount: float) -> PaymentResult:
        return PaymentResult(True, "ok")


class FakeDeclinedPayment(PaymentMethod):
    """Test double: always terminally fails (not retryable)."""

    @property
    def name(self) -> str:
        return "Fake Declined"

    def pay(self, amount: float) -> PaymentResult:
        return PaymentResult(False, "declined", "card_declined")


class FakeFlakyPayment(PaymentMethod):
    """Test double: fails with a transient error N times, then succeeds."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    @property
    def name(self) -> str:
        return "Fake Flaky"

    def pay(self, amount: float) -> PaymentResult:
        self.calls += 1
        if self.calls <= self.fail_times:
            return PaymentResult(False, "timeout", "gateway_timeout", transient=True)
        return PaymentResult(True, "ok")


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

    def test_credit_card_pay_succeeds_by_default(self):
        card = PaymentMethodRegistry.create(
            "credit_card", card_number="4111111111111234", cvv="123"
        )
        result = card.pay(100.0)
        self.assertTrue(result.success)
        self.assertEqual(card.name, "Credit Card")

    def test_credit_card_declined_test_number(self):
        card = PaymentMethodRegistry.create(
            "credit_card", card_number="4111111111110002", cvv="123"
        )
        result = card.pay(100.0)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "card_declined")
        self.assertFalse(result.transient)

    def test_credit_card_timeout_is_transient(self):
        card = PaymentMethodRegistry.create(
            "credit_card", card_number="4111111111110119", cvv="123"
        )
        result = card.pay(100.0)
        self.assertFalse(result.success)
        self.assertTrue(result.transient)

    def test_upi_over_limit_fails(self):
        upi = PaymentMethodRegistry.create("upi", upi_id="user@bank")
        result = upi.pay(200_000.0)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "limit_exceeded")

    def test_upi_invalid_id_fails(self):
        upi = PaymentMethodRegistry.create("upi", upi_id="not-a-upi-id")
        result = upi.pay(100.0)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_upi_id")

    def test_wallet_insufficient_balance(self):
        wallet = PaymentMethodRegistry.create(
            "wallet", wallet_provider="Paytm", wallet_id="empty-1"
        )
        result = wallet.pay(50.0)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "insufficient_funds")


class TestPaymentProcessor(unittest.TestCase):
    def test_successful_payment_notifies_all_observers(self):
        processor = PaymentProcessor(FakeSuccessPayment())
        obs1, obs2 = RecordingObserver(), RecordingObserver()
        processor.attach(obs1)
        processor.attach(obs2)

        result = processor.process_payment(100.0)

        self.assertTrue(result.success)
        self.assertEqual(len(obs1.events), 1)
        self.assertEqual(len(obs2.events), 1)
        self.assertEqual(obs1.events[0]["amount"], 100.0)
        self.assertEqual(obs1.events[0]["method"], "Fake Success")

    def test_terminal_failure_does_not_notify_and_is_not_retried(self):
        payment = FakeDeclinedPayment()
        processor = PaymentProcessor(payment, max_retries=3, retry_backoff_seconds=0)
        obs = RecordingObserver()
        processor.attach(obs)

        result = processor.process_payment(100.0)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "card_declined")
        self.assertEqual(len(obs.events), 0)

    def test_transient_failure_is_retried_and_can_succeed(self):
        flaky = FakeFlakyPayment(fail_times=2)
        processor = PaymentProcessor(flaky, max_retries=3, retry_backoff_seconds=0)
        obs = RecordingObserver()
        processor.attach(obs)

        result = processor.process_payment(100.0)

        self.assertTrue(result.success)
        self.assertEqual(flaky.calls, 3)  # 1 initial + 2 retries
        self.assertEqual(len(obs.events), 1)

    def test_transient_failure_gives_up_after_max_retries(self):
        flaky = FakeFlakyPayment(fail_times=10)
        processor = PaymentProcessor(flaky, max_retries=2, retry_backoff_seconds=0)

        result = processor.process_payment(100.0)

        self.assertFalse(result.success)
        self.assertEqual(flaky.calls, 3)  # 1 initial + 2 retries, then gives up

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
        processor.set_payment_method(FakeDeclinedPayment())
        processor.process_payment(20.0)

        self.assertEqual(len(obs.events), 1)
        self.assertEqual(obs.events[0]["method"], "Fake Success")


class TestPersistenceAndIdempotency(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.store = TransactionStore(self.db_path)

    def tearDown(self):
        os.remove(self.db_path)

    def test_successful_payment_is_persisted(self):
        processor = PaymentProcessor(FakeSuccessPayment(), store=self.store)
        result = processor.process_payment(100.0)

        record = self.store.get(result.txn_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["amount"], 100.0)

    def test_failed_payment_is_also_persisted(self):
        processor = PaymentProcessor(FakeDeclinedPayment(), store=self.store,
                                      retry_backoff_seconds=0)
        result = processor.process_payment(100.0)

        record = self.store.get(result.txn_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error_code"], "card_declined")

    def test_idempotency_key_prevents_double_charge(self):
        payment = FakeSuccessPayment()
        processor = PaymentProcessor(payment, store=self.store)

        first = processor.process_payment(100.0, idempotency_key="order-1")
        second = processor.process_payment(100.0, idempotency_key="order-1")

        self.assertEqual(first.txn_id, second.txn_id)
        # Only one row should exist for this idempotency key.
        cached = self.store.find_by_idempotency_key("order-1")
        self.assertEqual(cached["txn_id"], first.txn_id)

    def test_different_idempotency_keys_charge_separately(self):
        processor = PaymentProcessor(FakeSuccessPayment(), store=self.store)

        first = processor.process_payment(100.0, idempotency_key="order-A")
        second = processor.process_payment(100.0, idempotency_key="order-B")

        self.assertNotEqual(first.txn_id, second.txn_id)


if __name__ == "__main__":
    unittest.main()
