# Payment Processing System — Strategy + Observer (Python)

A small, dependency-free Python project demonstrating how to build a
payment system with **pluggable payment methods** and **decoupled,
multi-channel notifications**, using two classic design patterns:

- **Strategy Pattern** → payment methods (Credit Card, UPI, Net Banking, ...)
- **Observer Pattern** → notifications (Email, SMS, Push, ...)

## Why these patterns?

| Problem | Without a pattern | With this design |
|---|---|---|
| Choosing a payment method | `if method == "credit_card": ... elif method == "upi": ...` | Any class implementing `PaymentMethod` can be swapped in at runtime — no conditionals |
| Notifying users | Payment code directly calls `send_email()`, `send_sms()` | `PaymentProcessor` just calls `observer.update()` on whatever is attached — it never imports concrete notifiers |
| Adding a new payment method or channel | Edit existing factory / processor code | Add a new class + one registry decorator. Existing code is untouched (Open/Closed Principle) |

## Project structure

```
smart_pay/
├── payment_methods.py      # Strategy interface + concrete methods + registry/factory
├── notifiers.py             # Observer interface + concrete notification channels
├── payment_processor.py     # Subject/Context — wires strategy + observers together
├── main.py                  # Runnable demo
├── test_smart_pay.py   # Unit tests (unittest, uses test doubles)
└── README.md
```

## How it fits together

```
PaymentMethodRegistry.create("upi", ...)  -->  PaymentMethod (Strategy)
                                                      │
                                                      ▼
                                             PaymentProcessor
                                            (holds 1 strategy,
                                             N observers)
                                                      │
                                     success? ──► notify all observers
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                             EmailNotifier       SMSNotifier       PushNotifier
                              (Observer)          (Observer)        (Observer)
```

`PaymentProcessor` only ever talks to the **abstract** `PaymentMethod` and
`PaymentObserver` interfaces — never to concrete classes. That's what keeps
payment logic and notification logic fully decoupled.

## Running it

Requires Python 3.8+, no external dependencies.

```bash
cd smart_pay

# Run the demo
python3 main.py

# Run the tests
python3 -m unittest test_smart_pay.py -v
```

## Extending the system

### Add a new payment method
No existing file needs to change except adding this new class (put it in
`payment_methods.py` or its own file):

```python
@PaymentMethodRegistry.register("crypto")
class CryptoPayment(PaymentMethod):
    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address

    @property
    def name(self) -> str:
        return "Crypto"

    def pay(self, amount: float) -> bool:
        print(f"[Crypto] Sending {amount} to {self.wallet_address} ...")
        return True
```

Use it immediately:

```python
crypto = PaymentMethodRegistry.create("crypto", wallet_address="0xABC...")
processor.set_payment_method(crypto)
processor.process_payment(75.0)
```

### Add a new notification channel

```python
class SlackNotifier(PaymentObserver):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def update(self, event):
        print(f"[Slack -> {self.webhook_url}] Payment received: {event}")
```

```python
processor.attach(SlackNotifier("https://hooks.slack.com/..."))
```

That's it — no changes to `PaymentProcessor`, `main.py`, or any other
payment method/notifier class. This is the Open/Closed Principle in action.

## Design patterns & SOLID principles used

- **Strategy Pattern** — `PaymentMethod` defines a common interface;
  `CreditCardPayment`, `UPIPayment`, `NetBankingPayment`, `WalletPayment` are
  interchangeable implementations selected/swapped at runtime.
- **Observer Pattern** — `PaymentProcessor` is the subject; `EmailNotifier`,
  `SMSNotifier`, `PushNotifier` are observers that subscribe/unsubscribe and
  get notified automatically on successful payments.
- **Registry/Factory** — `PaymentMethodRegistry` lets new payment methods
  register themselves via a decorator instead of editing a growing
  if/elif factory function.
- **Open/Closed Principle** — new payment methods and notifiers can be added
  without modifying `PaymentProcessor` or any existing method/notifier class.
- **Dependency Inversion** — `PaymentProcessor` depends only on the abstract
  `PaymentMethod` / `PaymentObserver` interfaces, never on concrete classes.

## One-line resume bullet

> Built a payment processing system in Python using Strategy and Observer
> design patterns for pluggable payment methods and decoupled multi-channel
> (Email/SMS) notifications, following SOLID design principles.

## 20-second interview pitch

> "I built a payment system where different payment methods — Credit Card,
> UPI, Net Banking — all implement a common interface, so I can swap between
> them at runtime using the Strategy pattern. When a payment succeeds, I use
> the Observer pattern to automatically notify multiple channels — Email and
> SMS — without the payment logic knowing anything about the notifiers. This
> keeps the code decoupled and easy to extend."
