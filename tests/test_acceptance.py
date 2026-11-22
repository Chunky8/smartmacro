from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.database import db_session, db_to_decimal, init_db
from backend.domain.validators import validate_ingredient_macros
from backend.seed import seed_database


def _create_ingredient(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    name: str,
    energy_kcal: str = "100.00",
    protein: str = "10.00",
    carbs: str = "10.00",
    sugar: str = "0.00",
    fat: str = "5.00",
    saturated_fat: str = "0.00",
    unsaturated_fat: str = "0.00",
    fiber: str = "2.00",
    salt: str = "0.50",
) -> dict:
    resp = client.post(
        "/api/ingredients",
        headers=admin_headers,
        json={
            "name": name,
            "energy_kcal": energy_kcal,
            "protein": protein,
            "carbs": carbs,
            "sugar": sugar,
            "fat": fat,
            "saturated_fat": saturated_fat,
            "unsaturated_fat": unsaturated_fat,
            "fiber": fiber,
            "salt": salt,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_ac1_proportional_calculation_and_rounding(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """AC1: 37 g of ingredient (12.50 g carbs, 4.00 g sugar, 1.25 g salt per 100 g)
    -> 4.63 g carbs, 1.48 g sugar, 0.46 g salt (ROUND_HALF_UP, no subset duplication)."""
    ing = _create_ingredient(
        client,
        admin_headers,
        name="AC1 Teszt Alapanyag",
        protein="10.00",
        carbs="12.50",
        sugar="4.00",
        fat="5.00",
        salt="1.25",
    )

    log_resp = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-22",
            "ingredient_id": ing["id"],
            "weight_g": "37.00",
        },
    )
    assert log_resp.status_code == 201, log_resp.text
    macros = log_resp.json()["macros"]
    assert Decimal(macros["carbs"]) == Decimal("4.63")
    assert Decimal(macros["sugar"]) == Decimal("1.48")
    assert Decimal(macros["salt"]) == Decimal("0.46")

    summary_resp = client.get("/api/logs/2026-11-22", headers=user_headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert Decimal(summary["totals"]["carbs"]) == Decimal("4.63")
    assert Decimal(summary["totals"]["sugar"]) == Decimal("1.48")
    assert Decimal(summary["totals"]["salt"]) == Decimal("0.46")


def test_ac2_daily_log_status_and_remaining_carbs(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """AC2: 50.00 g carb limit, logging 35.25 g carbs -> MEGFELELŐ, 14.75 g remaining."""
    prof_resp = client.put(
        "/api/profile",
        headers=user_headers,
        json={
            "daily_carb_limit": "50.00",
            "daily_protein_target": "120.00",
            "daily_fat_target": "70.00",
        },
    )
    assert prof_resp.status_code == 200

    ing = _create_ingredient(
        client,
        admin_headers,
        name="AC2 Szénhidrát Alapanyag",
        protein="5.00",
        carbs="35.25",
        sugar="5.00",
        fat="2.00",
    )
    log_resp = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-22",
            "ingredient_id": ing["id"],
            "weight_g": "100.00",
        },
    )
    assert log_resp.status_code == 201

    summary = client.get("/api/logs/2026-11-22", headers=user_headers).json()
    assert summary["status"] == "MEGFELELŐ"
    assert Decimal(summary["remaining_carbs"]) == Decimal("14.75")


def test_ac3_daily_limit_exact_and_exceeded(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """AC3: 50.00 g limit -> 50.00 g is MEGFELELŐ (0.00 remaining);
    50.01 g saves successfully and switches status to KERET_TÚLLÉPVE."""
    ing_50 = _create_ingredient(
        client,
        admin_headers,
        name="AC3 50g CH",
        protein="10.00",
        carbs="50.00",
        fat="5.00",
    )
    ing_tiny = _create_ingredient(
        client,
        admin_headers,
        name="AC3 0.01g CH",
        protein="0.00",
        carbs="1.00",
        fat="0.00",
    )

    r1 = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-23",
            "ingredient_id": ing_50["id"],
            "weight_g": "100.00",
        },
    )
    assert r1.status_code == 201

    s1 = client.get("/api/logs/2026-11-23", headers=user_headers).json()
    assert Decimal(s1["totals"]["carbs"]) == Decimal("50.00")
    assert Decimal(s1["remaining_carbs"]) == Decimal("0.00")
    assert s1["status"] == "MEGFELELŐ"

    # Add 1 g of 1.00 g/100g carb ingredient -> +0.01 g carbs
    r2 = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-23",
            "ingredient_id": ing_tiny["id"],
            "weight_g": "1.00",
        },
    )
    assert r2.status_code == 201

    s2 = client.get("/api/logs/2026-11-23", headers=user_headers).json()
    assert Decimal(s2["totals"]["carbs"]) == Decimal("50.01")
    assert Decimal(s2["remaining_carbs"]) == Decimal("-0.01")
    assert s2["status"] == "KERET_TÚLLÉPVE"


def test_ac4_boundary_100g_sum_and_max_subsets(
    client: TestClient, admin_headers: dict
):
    """AC4: Sum == 100.00 g, sugar == carbs, sat + unsat == fat -> accepted (201)."""
    resp = client.post(
        "/api/ingredients",
        headers=admin_headers,
        json={
            "name": "AC4 Határeset Alapanyag",
            "energy_kcal": "500.00",
            "protein": "25.00",
            "carbs": "30.00",
            "sugar": "30.00",
            "fat": "35.00",
            "saturated_fat": "15.00",
            "unsaturated_fat": "20.00",
            "fiber": "5.00",
            "salt": "5.00",
        },
    )
    assert resp.status_code == 201, resp.text


def test_ac5_invalid_macro_ratios_and_negative_values(
    client: TestClient, admin_headers: dict
):
    """AC5: Sum > 100g, sugar > carbs, sat + unsat > fat, or negative -> 422."""
    invalid_payloads = [
        {
            "name": "Túl sok makró",
            "protein": "40.00",
            "carbs": "40.00",
            "fat": "20.00",
            "fiber": "0.00",
            "salt": "0.01",
        },
        {
            "name": "Túl sok cukor",
            "protein": "10.00",
            "carbs": "10.00",
            "sugar": "10.01",
            "fat": "5.00",
        },
        {
            "name": "Túl sok zsírsav",
            "protein": "10.00",
            "carbs": "10.00",
            "fat": "10.00",
            "saturated_fat": "6.00",
            "unsaturated_fat": "4.01",
        },
        {
            "name": "Negatív fehérje",
            "protein": "-1.00",
            "carbs": "10.00",
            "fat": "5.00",
        },
    ]
    for payload in invalid_payloads:
        resp = client.post("/api/ingredients", headers=admin_headers, json=payload)
        assert resp.status_code == 422, f"Expected 422 for {payload['name']}, got {resp.status_code}"


def test_ac6_banned_ingredient_blocked_in_log_and_recipe(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """AC6: Banned ingredient (> 0.00 g) rejected with 422 naming the banned ingredient."""
    banned_ing = _create_ingredient(client, admin_headers, name="Földimogyoró")
    safe_ing = _create_ingredient(client, admin_headers, name="Csirkemell")

    ban_resp = client.post(
        "/api/profile/banned",
        headers=user_headers,
        json={"ingredient_id": banned_ing["id"]},
    )
    assert ban_resp.status_code == 201

    # Direct log of banned ingredient
    direct_log = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-24",
            "ingredient_id": banned_ing["id"],
            "weight_g": "25.00",
        },
    )
    assert direct_log.status_code == 422
    assert "Földimogyoró" in direct_log.json()["detail"]

    # Recipe containing banned ingredient
    recipe_resp = client.post(
        "/api/recipes",
        headers=user_headers,
        json={
            "name": "Mogyorós csirke",
            "servings": "2.00",
            "items": [
                {"ingredient_id": safe_ing["id"], "weight_g": "200.00"},
                {"ingredient_id": banned_ing["id"], "weight_g": "30.00"},
            ],
        },
    )
    assert recipe_resp.status_code == 201
    recipe_id = recipe_resp.json()["id"]

    recipe_log = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-24",
            "recipe_id": recipe_id,
            "servings": "1.00",
        },
    )
    assert recipe_log.status_code == 422
    assert "Földimogyoró" in recipe_log.json()["detail"]


def test_ac7_invalid_weight_rejected(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """AC7: weight_g <= 0.00 or > 5000.00 rejected with 422 in recipes and logs."""
    ing = _create_ingredient(client, admin_headers, name="AC7 Alapanyag")

    for bad_weight in ("0.00", "-10.00", "5000.01"):
        r_log = client.post(
            "/api/logs",
            headers=user_headers,
            json={
                "log_date": "2026-11-25",
                "ingredient_id": ing["id"],
                "weight_g": bad_weight,
            },
        )
        assert r_log.status_code == 422

        r_recipe = client.post(
            "/api/recipes",
            headers=user_headers,
            json={
                "name": "Hibás recept",
                "servings": "1.00",
                "items": [{"ingredient_id": ing["id"], "weight_g": bad_weight}],
            },
        )
        assert r_recipe.status_code == 422


def test_ac8_non_admin_forbidden_on_master_data(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """AC8: USER role receives 403 Forbidden on POST/PUT/DELETE /api/ingredients."""
    ing = _create_ingredient(client, admin_headers, name="AC8 Védett Alapanyag")

    post_resp = client.post(
        "/api/ingredients",
        headers=user_headers,
        json={
            "name": "Jogosulatlan",
            "protein": "10.00",
            "carbs": "10.00",
            "fat": "5.00",
        },
    )
    assert post_resp.status_code == 403

    put_resp = client.put(
        f"/api/ingredients/{ing['id']}",
        headers=user_headers,
        json={
            "name": "Módosított",
            "protein": "10.00",
            "carbs": "10.00",
            "fat": "5.00",
        },
    )
    assert put_resp.status_code == 403

    del_resp = client.delete(
        f"/api/ingredients/{ing['id']}",
        headers=user_headers,
    )
    assert del_resp.status_code == 403


def test_snapshot_immutability_after_ingredient_update(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """Updating an ingredient's macros must not alter previously saved daily_logs snapshots."""
    ing = _create_ingredient(
        client,
        admin_headers,
        name="Snapshot Alapanyag",
        protein="20.00",
        carbs="10.00",
        sugar="2.00",
        fat="5.00",
        salt="1.00",
    )

    log_resp = client.post(
        "/api/logs",
        headers=user_headers,
        json={
            "log_date": "2026-11-26",
            "ingredient_id": ing["id"],
            "weight_g": "100.00",
        },
    )
    assert log_resp.status_code == 201

    # Admin modifies the ingredient's carb content from 10.00 to 40.00
    upd_resp = client.put(
        f"/api/ingredients/{ing['id']}",
        headers=admin_headers,
        json={
            "name": "Snapshot Alapanyag",
            "energy_kcal": "300.00",
            "protein": "20.00",
            "carbs": "40.00",
            "sugar": "10.00",
            "fat": "5.00",
            "saturated_fat": "1.00",
            "unsaturated_fat": "3.00",
            "fiber": "2.00",
            "salt": "1.00",
        },
    )
    assert upd_resp.status_code == 200

    # Past daily log must still reflect the original 10.00 g carbs snapshot
    summary = client.get("/api/logs/2026-11-26", headers=user_headers).json()
    assert Decimal(summary["totals"]["carbs"]) == Decimal("10.00")
    assert Decimal(summary["totals"]["sugar"]) == Decimal("2.00")


def test_seed_database_populates_100_recipes_and_valid_ingredients(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """seed.py runs cleanly, creates admin + 3 test users, >=45 ingredients & 100 recipes,
    every seeded ingredient passes EU validation, and all seeded accounts can log in."""
    seed_db = str(tmp_path / "seed_verify.db")
    monkeypatch.setenv("SMARTMACRO_DB_PATH", seed_db)
    init_db(seed_db)
    seed_database(seed_db)

    with db_session(seed_db) as conn:
        ingredients = conn.execute("SELECT * FROM ingredients;").fetchall()
        recipe_count = conn.execute("SELECT COUNT(*) FROM recipes;").fetchone()[0]
        users = conn.execute("SELECT username, role FROM users ORDER BY id ASC;").fetchall()

    usernames = {u["username"]: u["role"] for u in users}
    assert usernames == {
        "admin": "ADMIN",
        "MakkMarci": "USER",
        "RegősBendegúz": "USER",
        "ToldiMiklós": "USER",
    }
    assert len(ingredients) >= 45
    assert recipe_count == 100

    for row in ingredients:
        validate_ingredient_macros(
            energy_kcal=db_to_decimal(row["energy_kcal"]),
            protein=db_to_decimal(row["protein"]),
            carbs=db_to_decimal(row["carbs"]),
            sugar=db_to_decimal(row["sugar"]),
            fat=db_to_decimal(row["fat"]),
            saturated_fat=db_to_decimal(row["saturated_fat"]),
            unsaturated_fat=db_to_decimal(row["unsaturated_fat"]),
            fiber=db_to_decimal(row["fiber"]),
            salt=db_to_decimal(row["salt"]),
        )

    # Verify login for admin and all 3 seeded test users
    from backend.main import app

    seed_client = TestClient(app)
    for uname, pw in [
        ("admin", "admin"),
        ("MakkMarci", "basic"),
        ("RegősBendegúz", "basic"),
        ("ToldiMiklós", "basic"),
    ]:
        r = seed_client.post("/api/auth/login", json={"username": uname, "password": pw})
        assert r.status_code == 200, f"Login failed for {uname}: {r.text}"


def test_auth_login_logout_and_invalid_credentials(client: TestClient):
    """Valid login returns token; invalid credentials return 401; logout invalidates token."""
    bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert ok.status_code == 200
    token = ok.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    out = client.post("/api/auth/logout", headers=headers)
    assert out.status_code == 204

    after_out = client.get("/api/auth/me", headers=headers)
    assert after_out.status_code == 401


def test_admin_creates_user_and_new_user_logs_in_with_basic(
    client: TestClient, admin_headers: dict, user_headers: dict
):
    """Only ADMIN can create/list users (USER gets 403); created user logs in with 'basic'."""
    forbidden_post = client.post(
        "/api/users", headers=user_headers, json={"username": "UjFelhasznalo"}
    )
    assert forbidden_post.status_code == 403

    forbidden_get = client.get("/api/users", headers=user_headers)
    assert forbidden_get.status_code == 403

    created = client.post(
        "/api/users", headers=admin_headers, json={"username": "KukoricaJancsi"}
    )
    assert created.status_code == 201
    assert created.json()["username"] == "KukoricaJancsi"
    assert created.json()["role"] == "USER"

    # Duplicate username -> 409 Conflict
    dup = client.post(
        "/api/users", headers=admin_headers, json={"username": "KukoricaJancsi"}
    )
    assert dup.status_code == 409

    # New user can log in with default password 'basic'
    login_resp = client.post(
        "/api/auth/login", json={"username": "KukoricaJancsi", "password": "basic"}
    )
    assert login_resp.status_code == 200

    # Admin can list users without password_hash exposed
    users_resp = client.get("/api/users", headers=admin_headers)
    assert users_resp.status_code == 200
    assert all("password_hash" not in u for u in users_resp.json())


def test_change_password_success_and_validation_errors(
    client: TestClient, user_headers: dict
):
    """Password change rejects wrong old password (401) and mismatched new passwords (422),
    and updates password hash on success."""
    # Mismatched new passwords -> 422
    mismatch = client.post(
        "/api/auth/change-password",
        headers=user_headers,
        json={
            "old_password": "basic",
            "new_password": "newpass123",
            "confirm_password": "different",
        },
    )
    assert mismatch.status_code == 422

    # Wrong old password -> 401
    wrong_old = client.post(
        "/api/auth/change-password",
        headers=user_headers,
        json={
            "old_password": "wrong_old",
            "new_password": "newpass123",
            "confirm_password": "newpass123",
        },
    )
    assert wrong_old.status_code == 401

    # Valid password change -> 200
    ok = client.post(
        "/api/auth/change-password",
        headers=user_headers,
        json={
            "old_password": "basic",
            "new_password": "uj_jelszo_2026",
            "confirm_password": "uj_jelszo_2026",
        },
    )
    assert ok.status_code == 200

    # Old password no longer works, new password works
    old_login = client.post(
        "/api/auth/login", json={"username": "MakkMarci", "password": "basic"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login", json={"username": "MakkMarci", "password": "uj_jelszo_2026"}
    )
    assert new_login.status_code == 200


def test_frontend_static_root_served(client: TestClient):
    """Root path '/' serves the Vanilla HTML/JS frontend."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SmartMacro" in resp.text
