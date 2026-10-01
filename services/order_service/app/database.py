"""주문 서비스만 접근하는 SQLite 저장소. 사용자 DB를 직접 읽지 않습니다."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    unit_price INTEGER NOT NULL CHECK (unit_price > 0),
                    total_price INTEGER NOT NULL CHECK (total_price > 0),
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)"
            )

    def check(self):
        with self.connect() as connection:
            connection.execute("SELECT id FROM orders LIMIT 1").fetchone()

    def create_order(
        self,
        user_id: int,
        product_name: str,
        quantity: int,
        unit_price: int,
        created_at: str,
    ) -> dict:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders
                (user_id, product_name, quantity, unit_price, total_price, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, product_name, quantity, unit_price, quantity * unit_price, created_at),
            )
            row = connection.execute(
                "SELECT * FROM orders WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)

    def get_order(self, order_id: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_orders(self, user_id: int | None, offset: int, limit: int) -> list[dict]:
        with self.connect() as connection:
            if user_id is None:
                rows = connection.execute(
                    "SELECT * FROM orders ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM orders WHERE user_id = ? ORDER BY id LIMIT ? OFFSET ?",
                    (user_id, limit, offset),
                ).fetchall()
            return [dict(row) for row in rows]
