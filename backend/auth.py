from dataclasses import dataclass
import hashlib
import hmac
import secrets
import sqlite3
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from backend.database import db_session

ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"
VALID_ROLES = {ROLE_USER, ROLE_ADMIN}

PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2-HMAC-SHA256 hash."""
    try:
        algo, salt, expected_hex = stored_hash.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(dk.hex(), expected_hex)


def create_session_token(conn: sqlite3.Connection, user_id: int) -> str:
    """Create and persist a new random session token for the given user."""
    token = secrets.token_hex(32)
    conn.execute(
        "INSERT INTO sessions (token, user_id) VALUES (?, ?);",
        (token, user_id),
    )
    return token


def delete_session_token(conn: sqlite3.Connection, token: str) -> None:
    """Invalidate a session token."""
    conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    username: str
    role: str
    token: str


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bejelentkezés szükséges (hiányzó Authorization fejléc).",
        )
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen Authorization fejléc formátum (Bearer <token> szükséges).",
        )
    return parts[1].strip()


def get_current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> CurrentUser:
    """Authenticate user via Bearer token stored in SQLite sessions table."""
    token = _extract_bearer_token(authorization)
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.role
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?;
            """,
            (token,),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Érvénytelen vagy lejárt munkamenet-token.",
        )
    return CurrentUser(
        user_id=int(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        token=token,
    )


def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Dependency enforcing ADMIN role for master data and user management."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin jogosultság szükséges ehhez a művelethez.",
        )
    return current_user
