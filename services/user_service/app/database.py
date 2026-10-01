"""사용자 서비스만 접근하는 SQLite 저장소."""

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
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )

    def check(self):
        with self.connect() as connection:
            connection.execute("SELECT id FROM users LIMIT 1").fetchone()

    def create_user(self, name: str, email: str, created_at: str) -> dict:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, created_at) VALUES (?, ?, ?)",
                (name, email, created_at),
            )
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)

    def get_user(self, user_id: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_users(self, offset: int, limit: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
            return [dict(row) for row in rows]
