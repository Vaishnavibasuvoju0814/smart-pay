"""
Demo entry point.

Run with:  python main.py
"""

from payment_methods import PaymentMethodRegistry
from notifiers import EmailNotifier, SMSNotifier, PushNotifier
from payment_processor import PaymentProcessor


def main():
    # 1. Pick a payment method dynamically (e.g. from user input / API request)
    credit_card = PaymentMethodRegistry.create(
        "credit_card", card_number="4111111111111234", cvv="123"
    )

    processor = PaymentProcessor(credit_card)

    # 2. Attach notification channels (Observer pattern)
    processor.attach(EmailNotifier("user@example.com"))
    processor.attach(SMSNotifier("+91-9876543210"))

    # 3. Process a payment
    processor.process_payment(2500.00)

    # --- Switch payment method at runtime (Strategy pattern) ---
    upi = PaymentMethodRegistry.create("upi", upi_id="user@okhdfcbank")
    processor.set_payment_method(upi)
    processor.process_payment(499.00)

    # --- Add a new notification channel with zero changes elsewhere ---
    push = PushNotifier("device-abc-123")
    processor.attach(push)

    net_banking = PaymentMethodRegistry.create(
        "net_banking", bank_name="HDFC Bank", account_number="00123456789"
    )
    processor.set_payment_method(net_banking)
    processor.process_payment(10999.50)

    # --- Detach a channel and use a brand new payment method (added later) ---
    processor.detach(push)
    wallet = PaymentMethodRegistry.create(
        "wallet", wallet_provider="Paytm", wallet_id="paytm-user-9988"
    )
    processor.set_payment_method(wallet)
    processor.process_payment(150.00)

    print("\nAvailable payment methods:", PaymentMethodRegistry.available_methods())


if __name__ == "__main__":
    main()
