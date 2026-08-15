"""
Thin FastAPI layer over the payment system.

This is what turns smart_pay from "a script you run" into "a service you
can call" -- the payment/notification logic itself is untouched; this file
only translates HTTP requests into calls against PaymentProcessor and
PaymentMethodRegistry.

Run with:
    uvicorn api:app --reload

Then open http://127.0.0.1:8000/docs for interactive Swagger docs.
"""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from notifiers import EmailNotifier, SMSNotifier
from payment_methods import PaymentMethodRegistry
from payment_processor import PaymentProcessor
from storage import TransactionStore

app = FastAPI(
    title="Smart Pay API",
    description="Multi-method payments with pluggable notifications.",
    version="1.0.0",
)

# One shared store so transactions persist across requests within a run.
store = TransactionStore()


class PaymentRequest(BaseModel):
    method: str = Field(..., description="e.g. credit_card, upi, net_banking, wallet",
                         json_schema_extra={"example": "credit_card"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 1500.0})
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Constructor args for the chosen payment method, e.g. "
                     "{'card_number': '...1234', 'cvv': '123'}",
    )
    email: Optional[str] = Field(None, description="If set, an email notification is sent on success")
    phone: Optional[str] = Field(None, description="If set, an SMS notification is sent on success")
    idempotency_key: Optional[str] = Field(
        None, description="Same key submitted twice returns the original result instead of re-charging"
    )


class PaymentResponse(BaseModel):
    txn_id: str
    status: str
    method: str
    amount: float
    message: str
    error_code: Optional[str] = None


def _to_response(processed) -> PaymentResponse:
    return PaymentResponse(
        txn_id=processed.txn_id,
        status="success" if processed.success else "failed",
        method=processed.method,
        amount=processed.amount,
        message=processed.message,
        error_code=processed.error_code,
    )


@app.get("/payment-methods")
def list_payment_methods() -> Dict[str, List[str]]:
    return {"methods": PaymentMethodRegistry.available_methods()}


@app.post("/payments", response_model=PaymentResponse)
def create_payment(req: PaymentRequest):
    try:
        payment_method = PaymentMethodRegistry.create(req.method, **req.details)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TypeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid 'details' for method '{req.method}': {exc}",
        )

    processor = PaymentProcessor(payment_method, store=store)
    if req.email:
        processor.attach(EmailNotifier(req.email))
    if req.phone:
        processor.attach(SMSNotifier(req.phone))

    processed = processor.process_payment(req.amount, idempotency_key=req.idempotency_key)

    if not processed.success:
        # 402 Payment Required communicates a declined/failed charge,
        # distinct from a 400 (bad request) or 500 (server error).
        raise HTTPException(
            status_code=402,
            detail={
                "txn_id": processed.txn_id,
                "error_code": processed.error_code,
                "message": processed.message,
            },
        )

    return _to_response(processed)


@app.get("/payments/{txn_id}", response_model=PaymentResponse)
def get_payment(txn_id: str):
    record = store.get(txn_id)
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return PaymentResponse(
        txn_id=record["txn_id"],
        status=record["status"],
        method=record["method"],
        amount=record["amount"],
        message=record["message"],
        error_code=record.get("error_code"),
    )


@app.get("/payments", response_model=List[PaymentResponse])
def list_payments(limit: int = 20):
    records = store.list_all(limit=limit)
    return [
        PaymentResponse(
            txn_id=r["txn_id"], status=r["status"], method=r["method"],
            amount=r["amount"], message=r["message"], error_code=r.get("error_code"),
        )
        for r in records
    ]
