from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient
import pytest

from backend.database import init_db
from backend.main import app


@pytest.fixture()
def test_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide an isolated, initialized (unseeded) SQLite database path per test."""
    db_file = tmp_path / "test_smartmacro.db"
    monkeypatch.setenv("SMARTMACRO_DB_PATH", str(db_file))
    init_db(str(db_file))
    return str(db_file)


@pytest.fixture()
def client(test_db_path: str) -> Iterator[TestClient]:
    """Provide a FastAPI TestClient bound to the isolated test database."""
    yield TestClient(app)


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"X-User-Id": "2", "X-User-Role": "ADMIN"}


@pytest.fixture()
def user_headers() -> dict[str, str]:
    return {"X-User-Id": "1", "X-User-Role": "USER"}
