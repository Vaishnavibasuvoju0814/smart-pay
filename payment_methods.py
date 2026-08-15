"""
Strategy Pattern implementation for payment methods.

Each payment method implements the same `PaymentMethod` interface so the
rest of the system (PaymentProcessor) can work with any of them
interchangeably, and new ones can be added without touching this file's
existing classes (Open/Closed Principle) via PaymentMethodRegistry.

Unlike a pure demo, `pay()` here simulates *real* failure modes (declines,
insufficient funds, expired cards, limits, gateway timeouts) using
deterministic test values -- similar to how Stripe/Razorpay expose test
card numbers that trigger specific outcomes. This makes failure paths
actually exercisable and testable, not just theoretical.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Type


@dataclass
class PaymentResult:
    """
    Outcome of a single payment attempt.

    `transient=True` marks errors worth retrying (e.g. a gateway timeout),
    as opposed to terminal errors like a declined card, which retrying
    would not fix.
    """
    success: bool
    message: str
    error_code: Optional[str] = None
    transient: bool = False


class PaymentMethod(ABC):
    """Strategy interface that every payment method must implement."""

    @abstractmethod
    def pay(self, amount: float) -> PaymentResult:
        """Attempt to process a payment of `amount`."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """Human readable name of the payment method."""
        raise NotImplementedError


class PaymentMethodRegistry:
    """
    A small factory/registry that lets new payment methods register
    themselves with a decorator instead of requiring edits to a central
    if/elif factory function. This keeps the factory Open for extension
    but Closed for modification.
    """

    _registry: Dict[str, Type["PaymentMethod"]] = {}

    @classmethod
    def register(cls, key: str):
        def decorator(payment_cls: Type["PaymentMethod"]):
            cls._registry[key.lower()] = payment_cls
            return payment_cls
        return decorator

    @classmethod
    def create(cls, key: str, **kwargs) -> "PaymentMethod":
        key = key.lower()
        if key not in cls._registry:
            available = ", ".join(cls._registry.keys()) or "(none registered)"
            raise ValueError(f"Unknown payment method '{key}'. Available: {available}")
        return cls._registry[key](**kwargs)

    @classmethod
    def available_methods(cls):
        return list(cls._registry.keys())


@PaymentMethodRegistry.register("credit_card")
class CreditCardPayment(PaymentMethod):
    """
    Test-card numbers (last 4 digits) that trigger specific outcomes,
    mirroring how real gateways (Stripe, etc.) expose test cards:

        ...0002  -> declined
        ...0341  -> insufficient funds
        ...0069  -> expired card
        ...0119  -> gateway timeout (transient -> will be retried)
        anything else -> approved
    """

    _OUTCOMES = {
        "0002": ("card_declined", "Your card was declined."),
        "0341": ("insufficient_funds", "Insufficient funds on card."),
        "0069": ("expired_card", "This card has expired."),
    }
    _TIMEOUT_SUFFIX = "0119"

    def __init__(self, card_number: str, cvv: str):
        self.card_number = card_number
        self.cvv = cvv

    @property
    def name(self) -> str:
        return "Credit Card"

    def pay(self, amount: float) -> PaymentResult:
        masked = f"**** **** **** {self.card_number[-4:]}"
        print(f"[CreditCard] Charging Rs.{amount:.2f} to card {masked} ...")

        last4 = self.card_number[-4:]

        if last4 == self._TIMEOUT_SUFFIX:
            print("[CreditCard] Gateway timeout.")
            return PaymentResult(False, "Gateway timed out. Please retry.",
                                  "gateway_timeout", transient=True)

        if last4 in self._OUTCOMES:
            code, msg = self._OUTCOMES[last4]
            print(f"[CreditCard] Declined ({code}).")
            return PaymentResult(False, msg, code)

        print("[CreditCard] Payment approved.")
        return PaymentResult(True, "Payment approved.")


@PaymentMethodRegistry.register("upi")
class UPIPayment(PaymentMethod):
    """
    Simulated real-world UPI constraints:
      - UPI IDs must contain '@' (e.g. user@bank)
      - Per-transaction limit of Rs.100,000 (typical real UPI cap)
      - A UPI ID starting with 'fail@' simulates the payee bank being down
        (transient -> will be retried)
    """

    TRANSACTION_LIMIT = 100_000.0

    def __init__(self, upi_id: str):
        self.upi_id = upi_id

    @property
    def name(self) -> str:
        return "UPI"

    def pay(self, amount: float) -> PaymentResult:
        print(f"[UPI] Requesting Rs.{amount:.2f} from UPI ID {self.upi_id} ...")

        if "@" not in self.upi_id:
            print("[UPI] Invalid UPI ID.")
            return PaymentResult(False, "Invalid UPI ID format.", "invalid_upi_id")

        if amount > self.TRANSACTION_LIMIT:
            print("[UPI] Limit exceeded.")
            return PaymentResult(
                False,
                f"Amount exceeds UPI per-transaction limit of Rs.{self.TRANSACTION_LIMIT:,.2f}.",
                "limit_exceeded",
            )

        if self.upi_id.startswith("fail@"):
            print("[UPI] Payee bank server unavailable.")
            return PaymentResult(False, "Payee bank server unavailable.",
                                  "bank_unavailable", transient=True)

        print("[UPI] Payment approved.")
        return PaymentResult(True, "Payment approved.")


@PaymentMethodRegistry.register("net_banking")
class NetBankingPayment(PaymentMethod):
    """
    A bank name of "Test Down Bank" simulates that bank's gateway being
    temporarily unreachable (transient -> will be retried).
    """

    DOWN_BANKS = {"test down bank"}

    def __init__(self, bank_name: str, account_number: str):
        self.bank_name = bank_name
        self.account_number = account_number

    @property
    def name(self) -> str:
        return "Net Banking"

    def pay(self, amount: float) -> PaymentResult:
        masked = f"XXXXXX{self.account_number[-4:]}"
        print(
            f"[NetBanking] Redirecting to {self.bank_name} for Rs.{amount:.2f} "
            f"(a/c {masked}) ..."
        )

        if self.bank_name.strip().lower() in self.DOWN_BANKS:
            print("[NetBanking] Bank gateway unavailable.")
            return PaymentResult(False, f"{self.bank_name} is currently unavailable.",
                                  "bank_unavailable", transient=True)

        if amount <= 0:
            print("[NetBanking] Invalid amount.")
            return PaymentResult(False, "Amount must be greater than zero.",
                                  "invalid_amount")

        print("[NetBanking] Payment approved.")
        return PaymentResult(True, "Payment approved.")


@PaymentMethodRegistry.register("wallet")
class WalletPayment(PaymentMethod):
    """
    A wallet_id containing 'empty' simulates an insufficient wallet
    balance -- demonstrates extensibility (added after the others,
    zero changes elsewhere) as well as another terminal failure mode.
    """

    def __init__(self, wallet_provider: str, wallet_id: str):
        self.wallet_provider = wallet_provider
        self.wallet_id = wallet_id

    @property
    def name(self) -> str:
        return f"{self.wallet_provider} Wallet"

    def pay(self, amount: float) -> PaymentResult:
        print(
            f"[Wallet] Debiting Rs.{amount:.2f} from {self.wallet_provider} "
            f"wallet {self.wallet_id} ..."
        )

        if "empty" in self.wallet_id.lower():
            print("[Wallet] Insufficient balance.")
            return PaymentResult(False, "Insufficient wallet balance.",
                                  "insufficient_funds")

        print("[Wallet] Payment approved.")
        return PaymentResult(True, "Payment approved.")
