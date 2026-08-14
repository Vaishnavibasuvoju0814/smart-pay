"""
Strategy Pattern implementation for payment methods.

Each payment method implements the same `PaymentMethod` interface so the
rest of the system (PaymentProcessor) can work with any of them
interchangeably, and new ones can be added without touching this file's
existing classes (Open/Closed Principle) via PaymentMethodRegistry.
"""

from abc import ABC, abstractmethod
from typing import Dict, Type


class PaymentMethod(ABC):
    """Strategy interface that every payment method must implement."""

    @abstractmethod
    def pay(self, amount: float) -> bool:
        """Process a payment of `amount`. Returns True on success."""
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
    def __init__(self, card_number: str, cvv: str):
        self.card_number = card_number
        self.cvv = cvv

    @property
    def name(self) -> str:
        return "Credit Card"

    def pay(self, amount: float) -> bool:
        masked = f"**** **** **** {self.card_number[-4:]}"
        print(f"[CreditCard] Charging Rs.{amount:.2f} to card {masked} ...")
        # Simulated payment gateway call would go here.
        print("[CreditCard] Payment approved.")
        return True


@PaymentMethodRegistry.register("upi")
class UPIPayment(PaymentMethod):
    def __init__(self, upi_id: str):
        self.upi_id = upi_id

    @property
    def name(self) -> str:
        return "UPI"

    def pay(self, amount: float) -> bool:
        print(f"[UPI] Requesting Rs.{amount:.2f} from UPI ID {self.upi_id} ...")
        print("[UPI] Payment approved.")
        return True


@PaymentMethodRegistry.register("net_banking")
class NetBankingPayment(PaymentMethod):
    def __init__(self, bank_name: str, account_number: str):
        self.bank_name = bank_name
        self.account_number = account_number

    @property
    def name(self) -> str:
        return "Net Banking"

    def pay(self, amount: float) -> bool:
        masked = f"XXXXXX{self.account_number[-4:]}"
        print(
            f"[NetBanking] Redirecting to {self.bank_name} for Rs.{amount:.2f} "
            f"(a/c {masked}) ..."
        )
        print("[NetBanking] Payment approved.")
        return True


# --- Example of adding a brand new method WITHOUT touching anything above ---
@PaymentMethodRegistry.register("wallet")
class WalletPayment(PaymentMethod):
    """Demonstrates extensibility: added later, zero changes elsewhere."""

    def __init__(self, wallet_provider: str, wallet_id: str):
        self.wallet_provider = wallet_provider
        self.wallet_id = wallet_id

    @property
    def name(self) -> str:
        return f"{self.wallet_provider} Wallet"

    def pay(self, amount: float) -> bool:
        print(
            f"[Wallet] Debiting Rs.{amount:.2f} from {self.wallet_provider} "
            f"wallet {self.wallet_id} ..."
        )
        print("[Wallet] Payment approved.")
        return True
