"""
CLI demo covering: success paths, terminal failures (declined card, UPI
limit, insufficient wallet balance), a transient failure that gets
auto-retried and then succeeds, idempotent replay of the same request,
and persisted transaction history.

Run with:  python main.py
"""

from payment_methods import PaymentMethodRegistry
from notifiers import EmailNotifier, SMSNotifier, PushNotifier
from payment_processor import PaymentProcessor
from storage import TransactionStore


def main():
    # A real, on-disk SQLite store -- transactions survive after this script exits.
    store = TransactionStore("smart_pay.db")

    # 1. A normal successful payment.
    credit_card = PaymentMethodRegistry.create(
        "credit_card", card_number="4111111111111234", cvv="123"
    )
    processor = PaymentProcessor(credit_card, store=store)
    processor.attach(EmailNotifier("user@example.com"))
    processor.attach(SMSNotifier("+91-9876543210"))
    processor.process_payment(2500.00)

    # 2. A terminal failure: this test card number is a known "declined" case.
    declined_card = PaymentMethodRegistry.create(
        "credit_card", card_number="4111111111110002", cvv="123"
    )
    processor.set_payment_method(declined_card)
    processor.process_payment(499.00)

    # 3. A transient failure that gets auto-retried and succeeds/fails cleanly.
    #    This card number simulates a gateway timeout on every attempt, so
    #    you'll see the processor retry up to `max_retries` times.
    flaky_card = PaymentMethodRegistry.create(
        "credit_card", card_number="4111111111110119", cvv="123"
    )
    processor.set_payment_method(flaky_card)
    processor.process_payment(750.00)

    # 4. UPI over the simulated transaction limit -- terminal failure, no retry.
    upi = PaymentMethodRegistry.create("upi", upi_id="user@okhdfcbank")
    processor.set_payment_method(upi)
    processor.process_payment(150_000.00)

    # 5. Idempotency: submitting the *same* idempotency_key twice only
    #    charges once -- the second call returns the cached result.
    valid_upi = PaymentMethodRegistry.create("upi", upi_id="user@okhdfcbank")
    processor.set_payment_method(valid_upi)
    key = "order-9d2f-checkout"
    processor.process_payment(999.00, idempotency_key=key)
    processor.process_payment(999.00, idempotency_key=key)  # no second charge

    # 6. Insufficient wallet balance -- another terminal failure mode.
    empty_wallet = PaymentMethodRegistry.create(
        "wallet", wallet_provider="Paytm", wallet_id="empty-wallet-1"
    )
    processor.set_payment_method(empty_wallet)
    processor.attach(PushNotifier("device-abc-123"))
    processor.process_payment(150.00)

    # 7. Show that everything above was actually persisted.
    print("\n=== Persisted transaction history (from smart_pay.db) ===")
    for row in store.list_all(limit=10):
        print(f"  {row['created_at']}  {row['txn_id']}  {row['method']:<15} "
              f"Rs.{row['amount']:>10.2f}  {row['status']:<7} "
              f"{row['error_code'] or ''}")


if __name__ == "__main__":
    main()
