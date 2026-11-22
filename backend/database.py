from contextlib import contextmanager
from decimal import Decimal
import os
import sqlite3
from typing import Iterator, Optional

DEFAULT_DB_PATH = os.environ.get("SMARTMACRO_DB_PATH", "smartmacro.db")


def decimal_to_db(value: Decimal) -> str:
    """Serialize a Decimal to TEXT for lossless SQLite storage."""
    if not isinstance(value, Decimal):
        raise TypeError(f"Csak Decimal tárolható, kapott típus: {type(value).__name__}.")
    return format(value, "f")


def db_to_decimal(value: str | Decimal | None) -> Decimal:
    """Deserialize a TEXT value from SQLite back into Decimal."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create a configured sqlite3 connection with foreign keys enabled."""
    path = db_path or os.environ.get("SMARTMACRO_DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a sqlite3 connection with automatic commit/rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize all SmartMacro SQLite tables using parameterized/DDL SQL."""
    with db_session(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'USER',
                daily_carb_limit TEXT NOT NULL DEFAULT '50.00',
                daily_protein_target TEXT NOT NULL DEFAULT '100.00',
                daily_fat_target TEXT NOT NULL DEFAULT '70.00'
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                energy_kcal TEXT NOT NULL DEFAULT '0.00',
                protein TEXT NOT NULL,
                carbs TEXT NOT NULL,
                sugar TEXT NOT NULL DEFAULT '0.00',
                fat TEXT NOT NULL,
                saturated_fat TEXT NOT NULL DEFAULT '0.00',
                unsaturated_fat TEXT NOT NULL DEFAULT '0.00',
                fiber TEXT NOT NULL DEFAULT '0.00',
                salt TEXT NOT NULL DEFAULT '0.00',
                is_verified INTEGER NOT NULL DEFAULT 1
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS banned_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                UNIQUE(user_id, ingredient_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                servings TEXT NOT NULL DEFAULT '1.00',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recipe_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                weight_g TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                log_date TEXT NOT NULL,
                meal_name TEXT NOT NULL,
                ingredient_id INTEGER,
                recipe_id INTEGER,
                weight_g TEXT,
                servings TEXT,
                energy_kcal TEXT NOT NULL DEFAULT '0.00',
                protein TEXT NOT NULL,
                carbs TEXT NOT NULL,
                sugar TEXT NOT NULL,
                fat TEXT NOT NULL,
                saturated_fat TEXT NOT NULL DEFAULT '0.00',
                unsaturated_fat TEXT NOT NULL DEFAULT '0.00',
                fiber TEXT NOT NULL DEFAULT '0.00',
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE SET NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE SET NULL
            );
            """
        )
