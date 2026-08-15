# Smart Pay — Multi-Method Payment Processing System (Python)

A Python payment processing system with **pluggable payment methods**,
**decoupled multi-channel notifications**, **real failure handling with
retries**, **idempotency**, **SQLite persistence**, and an optional
**REST API layer** — built around the Strategy and Observer design
patterns.

## What changed from a plain "design patterns demo"

An earlier version of this project only demonstrated Strategy + Observer
with `pay()` unconditionally returning `True`. This version closes the gap
between "demo" and "system":

| Concern | How it's handled now |
|---|---|
| Realistic failures | Deterministic test values simulate declines, insufficient funds, expired cards, invalid IDs, transaction limits — not just always-succeed |
| Transient vs terminal errors | `PaymentResult.transient` distinguishes a gateway timeout (worth retrying) from a decline (retrying won't help) |
| Retries | `PaymentProcessor` automatically retries transient failures with backoff, up to a configurable limit |
| Double-charging | Idempotency keys — the same key submitted twice returns the cached result instead of charging again |
| Persistence | Every attempt (success or failure) is saved to SQLite via `TransactionStore`, so state survives a restart |
| Being callable as a service | `api.py` wraps everything in a FastAPI app with `/payments` endpoints |

## Project structure

```
smart_pay/
├── payment_methods.py      # Strategy interface + concrete methods + registry/factory
├── notifiers.py             # Observer interface + concrete notification channels
├── payment_processor.py     # Subject/Context — retries, idempotency, persistence, notifications
├── storage.py                # SQLite-backed TransactionStore
├── api.py                    # Optional FastAPI layer exposing payments over HTTP
├── main.py                   # Runnable CLI demo covering success + every failure mode
├── test_payment_system.py    # 18 unit tests (unittest, test doubles, temp SQLite DB)
├── requirements.txt          # Only needed for api.py (fastapi, uvicorn)
└── README.md
```

## Running it

Requires Python 3.8+. The core library and CLI demo need **no external
packages** — only `api.py` needs FastAPI/uvicorn.

```bash
cd smart_pay

# Run the CLI demo (success + every failure mode + retries + idempotency)
python3 main.py

# Run the tests
python3 -m unittest test_payment_system.py -v

# Optional: run the API
pip install -r requirements.txt --break-system-packages   # if needed
uvicorn api:app --reload
# then open http://127.0.0.1:8000/docs for interactive Swagger UI
```

## Testing failure paths yourself

The payment methods use **deterministic test values** (similar to how
Stripe/Razorpay expose test cards) so failures are reproducible, not
random:

| Method | Trigger | Result |
|---|---|---|
| Credit Card | card number ending `0002` | declined |
| Credit Card | card number ending `0341` | insufficient funds |
| Credit Card | card number ending `0069` | expired card |
| Credit Card | card number ending `0119` | gateway timeout (**retried automatically**) |
| UPI | amount > Rs.100,000 | limit exceeded |
| UPI | ID without `@` | invalid UPI ID |
| UPI | ID starting with `fail@` | bank unavailable (**retried automatically**) |
| Net Banking | bank name `"Test Down Bank"` | bank unavailable (**retried automatically**) |
| Wallet | wallet ID containing `"empty"` | insufficient balance |

Any other value succeeds.

## API quick reference

```bash
# List available payment methods
curl http://127.0.0.1:8000/payment-methods

# Make a payment
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{
        "method": "credit_card",
        "amount": 500,
        "details": {"card_number": "4111111111111234", "cvv": "123"},
        "email": "user@example.com",
        "idempotency_key": "order-123"
      }'

# Look up a transaction
curl http://127.0.0.1:8000/payments/{txn_id}

# List recent transactions
curl http://127.0.0.1:8000/payments?limit=20
```

A declined/failed payment returns **HTTP 402 Payment Required** with the
error code and message in the response body — distinct from a 400 (bad
request) or 500 (server error).

## How it fits together

```
PaymentMethodRegistry.create("upi", ...) --> PaymentMethod (Strategy)
                                                    │
                                                    ▼
                       idempotency check ──►  PaymentProcessor
                       (via TransactionStore)  (retries transient
                                                 failures, persists
                                                 every attempt)
                                                    │
                                    success? ──► notify all observers
                                                    │
                                  ┌─────────────────┼─────────────────┐
                                  ▼                 ▼                 ▼
                           EmailNotifier       SMSNotifier       PushNotifier
                            (Observer)          (Observer)        (Observer)
```

`PaymentProcessor` only ever talks to the **abstract** `PaymentMethod` and
`PaymentObserver` interfaces — never concrete classes — which is what keeps
payment logic and notification logic decoupled. `storage.py` is similarly
isolated behind a small interface, so swapping SQLite for Postgres later
means changing one file, not the business logic.

## Extending the system

### Add a new payment method
```python
@PaymentMethodRegistry.register("crypto")
class CryptoPayment(PaymentMethod):
    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address

    @property
    def name(self) -> str:
        return "Crypto"

    def pay(self, amount: float) -> PaymentResult:
        print(f"[Crypto] Sending {amount} to {self.wallet_address} ...")
        return PaymentResult(True, "Payment approved.")
```
No other file needs to change — `main.py`, `api.py`, and `PaymentProcessor`
all pick it up automatically via the registry.

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

## Design patterns & principles used

- **Strategy Pattern** — `PaymentMethod` defines a common interface;
  Credit Card, UPI, Net Banking, Wallet are interchangeable implementations
  selected/swapped at runtime.
- **Observer Pattern** — `PaymentProcessor` is the subject; Email, SMS,
  Push notifiers subscribe/unsubscribe and get notified automatically on
  successful payments.
- **Registry/Factory** — `PaymentMethodRegistry` lets new payment methods
  register themselves via a decorator instead of editing a growing
  if/elif factory function.
- **Open/Closed Principle** — new payment methods and notifiers can be
  added without modifying `PaymentProcessor` or any existing class.
- **Dependency Inversion** — `PaymentProcessor` depends only on abstract
  `PaymentMethod` / `PaymentObserver` / persistence interfaces, never
  concrete classes.
- **Idempotency** — a standard technique in real payment APIs (Stripe,
  Razorpay) to make retried client requests safe.

## Known limitations (being upfront about what this still isn't)

This is a well-architected simulation, not a production payment system.
It does **not**:
- Call a real payment gateway over the network
- Handle concurrent requests safely at the database level (no row locking)
- Implement authentication/authorization on the API
- Encrypt or tokenize card data (real systems never store raw card numbers
  at all — this project prints a masked number purely for demo output)
- Handle partial refunds, chargebacks, or webhooks

These would be the natural next additions if extending this further.

## One-line resume bullet

> Built a Python payment processing system with pluggable payment methods
> (Strategy pattern), decoupled multi-channel notifications (Observer
> pattern), retry logic for transient failures, idempotent request
> handling, SQLite persistence, and a FastAPI service layer.

## 20-second interview pitch

> "I built a payment system where different payment methods — Credit
> Card, UPI, Net Banking — implement a common interface via the Strategy
> pattern, so they're swappable at runtime. On success, the Observer
> pattern notifies Email/SMS/Push channels without payment logic knowing
> about them. I also modeled realistic failure handling: transient errors
> like gateway timeouts get retried automatically, terminal errors like
> declines don't, idempotency keys prevent double-charging on retried
> requests, every transaction persists to SQLite, and I wrapped it in a
> FastAPI layer so it's callable as an actual service, not just a script."
