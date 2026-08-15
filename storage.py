"""
Persistence layer for transactions, backed by SQLite.

Kept deliberately separate from PaymentProcessor: the processor only calls
`store.save(...)` and `store.find_by_idempotency_key(...)` through this
thin interface, so swapping SQLite for Postgres/Mongo later means changing
this one file, not the business logic.
"""

import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = "smart_pay.db"


class TransactionStore:
    """Simple SQLite-backed store for payment transactions."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    txn_id           TEXT PRIMARY KEY,
                    idempotency_key  TEXT UNIQUE,
                    amount           REAL NOT NULL,
                    method           TEXT NOT NULL,
                    status           TEXT NOT NULL,
                    error_code       TEXT,
                    message          TEXT,
                    created_at       TEXT NOT NULL
                )
                """
            )

    def save(self, record: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO transactions
                    (txn_id, idempotency_key, amount, method, status,
                     error_code, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["txn_id"],
                    record.get("idempotency_key"),
                    record["amount"],
                    record["method"],
                    record["status"],
                    record.get("error_code"),
                    record.get("message"),
                    record["created_at"],
                ),
            )

    def get(self, txn_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM transactions WHERE txn_id = ?", (txn_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM transactions WHERE idempotency_key = ?", (key,)
            ).fetchone()
            return dict(row) if row else None

    def list_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
