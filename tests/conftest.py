from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient
import pytest

from backend.auth import hash_password
from backend.database import db_session, init_db
from backend.main import app


@pytest.fixture()
def test_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide an isolated, initialized (unseeded) SQLite database with test accounts."""
    db_file = tmp_path / "test_smartmacro.db"
    monkeypatch.setenv("SMARTMACRO_DB_PATH", str(db_file))
    init_db(str(db_file))
    with db_session(str(db_file)) as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, daily_carb_limit, daily_protein_target, daily_fat_target)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("MakkMarci", hash_password("basic"), "USER", "50.00", "120.00", "70.00"),
        )
        conn.execute(
            """
            INSERT INTO users (username, password_hash, role, daily_carb_limit, daily_protein_target, daily_fat_target)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("admin", hash_password("admin"), "ADMIN", "50.00", "120.00", "70.00"),
        )
    return str(db_file)


@pytest.fixture()
def client(test_db_path: str) -> Iterator[TestClient]:
    """Provide a FastAPI TestClient bound to the isolated test database."""
    yield TestClient(app)


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/auth/login",
        json={"username": "MakkMarci", "password": "basic"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
