"""SQLite persistence and sample records for the resolution agent."""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3


SAMPLE_ORDERS = (
    ("DEMO-1001", "Alex Morgan", "alex@example.test", "SMART-SPEAKER", "Smart Speaker", 79.99, 1),
    ("DEMO-1002", "Jamie Chen", "jamie@example.test", "BLUE-CHAIR", "Blue Chair", 149.50, 1),
    ("DEMO-1003", "Taylor Singh", "taylor@example.test", "COFFEE-MAKER", "Coffee Maker", 59.00, 0),
)

SAMPLE_INVENTORY = (
    ("SMART-SPEAKER", "Smart Speaker", 3),
    ("BLUE-CHAIR", "Blue Chair", 0),
    ("COFFEE-MAKER", "Coffee Maker", 2),
)


class Database:
    def __init__(self, path=None):
        configured_path = path or os.getenv("AGENT_DB_PATH")
        self.path = Path(configured_path) if configured_path else Path(__file__).with_name("agent.db")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    total REAL NOT NULL CHECK (total >= 0),
                    exchange_eligible INTEGER NOT NULL CHECK (exchange_eligible IN (0, 1)),
                    status TEXT NOT NULL DEFAULT 'placed'
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    item_id TEXT PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0)
                );
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_reference TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE REFERENCES orders(order_id),
                    amount REAL NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS exchanges (
                    exchange_reference TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL UNIQUE REFERENCES orders(order_id),
                    item_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    message TEXT NOT NULL,
                    delivery_status TEXT NOT NULL DEFAULT 'simulated',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.executemany(
                """
                INSERT OR IGNORE INTO orders
                    (order_id, customer_name, email, item_id, item_name, total, exchange_eligible)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                SAMPLE_ORDERS,
            )
            conn.executemany(
                "INSERT OR IGNORE INTO inventory (item_id, item_name, quantity) VALUES (?, ?, ?)",
                SAMPLE_INVENTORY,
            )
            conn.commit()
