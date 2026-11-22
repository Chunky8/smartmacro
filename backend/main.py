from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
import sqlite3
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.auth import CurrentUser, get_current_user, require_admin
from backend.database import db_session, db_to_decimal, decimal_to_db, init_db
from backend.domain.calculator import (
    MacroProfile,
    WeightedIngredient,
    calculate_composite_macros,
    calculate_item_macros,
    calculate_per_serving_macros,
    evaluate_daily_carb_status,
    scale_macros_unrounded,
    sum_daily_snapshots,
)
from backend.schemas import (
    BannedIngredientCreate,
    BannedIngredientResponse,
    DailyLogCreate,
    DailyLogResponse,
    DailySummaryResponse,
    IngredientCreate,
    IngredientResponse,
    IngredientUpdate,
    MacroSnapshot,
    RecipeCreate,
    RecipeItemResponse,
    RecipeResponse,
    UserProfileResponse,
    UserProfileUpdate,
)
from backend.seed import seed_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_database()
    yield


app = FastAPI(title="SmartMacro API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _row_to_macro_profile(row: sqlite3.Row) -> MacroProfile:
    return MacroProfile(
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


def _profile_to_snapshot(profile: MacroProfile) -> MacroSnapshot:
    return MacroSnapshot(
        energy_kcal=profile.energy_kcal,
        protein=profile.protein,
        carbs=profile.carbs,
        sugar=profile.sugar,
        fat=profile.fat,
        saturated_fat=profile.saturated_fat,
        unsaturated_fat=profile.unsaturated_fat,
        fiber=profile.fiber,
        salt=profile.salt,
    )


def _row_to_ingredient(row: sqlite3.Row) -> IngredientResponse:
    return IngredientResponse(
        id=row["id"],
        name=row["name"],
        energy_kcal=db_to_decimal(row["energy_kcal"]),
        protein=db_to_decimal(row["protein"]),
        carbs=db_to_decimal(row["carbs"]),
        sugar=db_to_decimal(row["sugar"]),
        fat=db_to_decimal(row["fat"]),
        saturated_fat=db_to_decimal(row["saturated_fat"]),
        unsaturated_fat=db_to_decimal(row["unsaturated_fat"]),
        fiber=db_to_decimal(row["fiber"]),
        salt=db_to_decimal(row["salt"]),
        is_verified=bool(row["is_verified"]),
    )


def _ensure_user_exists(conn: sqlite3.Connection, current_user: CurrentUser) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?;", (current_user.user_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO users (id, username, role, daily_carb_limit, daily_protein_target, daily_fat_target)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                current_user.user_id,
                f"user_{current_user.user_id}",
                current_user.role,
                "50.00",
                "120.00",
                "70.00",
            ),
        )
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?;", (current_user.user_id,)
        ).fetchone()
    return row


def _build_recipe_response(conn: sqlite3.Connection, recipe_row: sqlite3.Row) -> RecipeResponse:
    item_rows = conn.execute(
        """
        SELECT ri.ingredient_id, ri.weight_g, i.name AS ingredient_name,
               i.energy_kcal, i.protein, i.carbs, i.sugar, i.fat,
               i.saturated_fat, i.unsaturated_fat, i.fiber, i.salt
        FROM recipe_items ri
        JOIN ingredients i ON i.id = ri.ingredient_id
        WHERE ri.recipe_id = ?
        ORDER BY ri.id ASC;
        """,
        (recipe_row["id"],),
    ).fetchall()

    weighted_items: list[WeightedIngredient] = []
    item_responses: list[RecipeItemResponse] = []
    for r in item_rows:
        weight = db_to_decimal(r["weight_g"])
        weighted_items.append(WeightedIngredient(_row_to_macro_profile(r), weight))
        item_responses.append(
            RecipeItemResponse(
                ingredient_id=r["ingredient_id"],
                ingredient_name=r["ingredient_name"],
                weight_g=weight,
            )
        )

    servings = db_to_decimal(recipe_row["servings"])
    total_macros = calculate_composite_macros(weighted_items)
    per_serving_macros = calculate_per_serving_macros(weighted_items, servings)

    return RecipeResponse(
        id=recipe_row["id"],
        user_id=recipe_row["user_id"],
        name=recipe_row["name"],
        servings=servings,
        items=item_responses,
        total_macros=_profile_to_snapshot(total_macros),
        per_serving_macros=_profile_to_snapshot(per_serving_macros),
    )


# ---------------------------------------------------------------------------
# Ingredients (master data)
# ---------------------------------------------------------------------------


@app.get("/api/ingredients", response_model=List[IngredientResponse])
def list_ingredients(search: Optional[str] = Query(default=None)):
    with db_session() as conn:
        if search:
            rows = conn.execute(
                "SELECT * FROM ingredients WHERE LOWER(name) LIKE LOWER(?) ORDER BY name ASC;",
                (f"%{search}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ingredients ORDER BY name ASC;"
            ).fetchall()
        return [_row_to_ingredient(r) for r in rows]


@app.post(
    "/api/ingredients",
    response_model=IngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ingredient(
    payload: IngredientCreate,
    _admin: CurrentUser = Depends(require_admin),
):
    with db_session() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO ingredients
                    (name, energy_kcal, protein, carbs, sugar, fat,
                     saturated_fat, unsaturated_fat, fiber, salt, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    payload.name,
                    decimal_to_db(payload.energy_kcal),
                    decimal_to_db(payload.protein),
                    decimal_to_db(payload.carbs),
                    decimal_to_db(payload.sugar),
                    decimal_to_db(payload.fat),
                    decimal_to_db(payload.saturated_fat),
                    decimal_to_db(payload.unsaturated_fat),
                    decimal_to_db(payload.fiber),
                    decimal_to_db(payload.salt),
                    1,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Már létezik ilyen nevű alapanyag: '{payload.name}'.",
            ) from exc

        row = conn.execute(
            "SELECT * FROM ingredients WHERE id = ?;", (cursor.lastrowid,)
        ).fetchone()
        return _row_to_ingredient(row)


@app.put("/api/ingredients/{ingredient_id}", response_model=IngredientResponse)
def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    _admin: CurrentUser = Depends(require_admin),
):
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM ingredients WHERE id = ?;", (ingredient_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Az alapanyag nem található.",
            )
        try:
            conn.execute(
                """
                UPDATE ingredients
                SET name = ?, energy_kcal = ?, protein = ?, carbs = ?, sugar = ?,
                    fat = ?, saturated_fat = ?, unsaturated_fat = ?, fiber = ?, salt = ?
                WHERE id = ?;
                """,
                (
                    payload.name,
                    decimal_to_db(payload.energy_kcal),
                    decimal_to_db(payload.protein),
                    decimal_to_db(payload.carbs),
                    decimal_to_db(payload.sugar),
                    decimal_to_db(payload.fat),
                    decimal_to_db(payload.saturated_fat),
                    decimal_to_db(payload.unsaturated_fat),
                    decimal_to_db(payload.fiber),
                    decimal_to_db(payload.salt),
                    ingredient_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Már létezik ilyen nevű alapanyag: '{payload.name}'.",
            ) from exc

        row = conn.execute(
            "SELECT * FROM ingredients WHERE id = ?;", (ingredient_id,)
        ).fetchone()
        return _row_to_ingredient(row)


@app.delete(
    "/api/ingredients/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ingredient(
    ingredient_id: int,
    _admin: CurrentUser = Depends(require_admin),
):
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM ingredients WHERE id = ?;", (ingredient_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Az alapanyag nem található.",
            )
        try:
            conn.execute("DELETE FROM ingredients WHERE id = ?;", (ingredient_id,))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Az alapanyag receptben szerepel, ezért nem törölhető.",
            ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# User profile & banned ingredients
# ---------------------------------------------------------------------------


@app.get("/api/profile", response_model=UserProfileResponse)
def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    with db_session() as conn:
        row = _ensure_user_exists(conn, current_user)
        return UserProfileResponse(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            daily_carb_limit=db_to_decimal(row["daily_carb_limit"]),
            daily_protein_target=db_to_decimal(row["daily_protein_target"]),
            daily_fat_target=db_to_decimal(row["daily_fat_target"]),
        )


@app.put("/api/profile", response_model=UserProfileResponse)
def update_profile(
    payload: UserProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        _ensure_user_exists(conn, current_user)
        conn.execute(
            """
            UPDATE users
            SET daily_carb_limit = ?, daily_protein_target = ?, daily_fat_target = ?
            WHERE id = ?;
            """,
            (
                decimal_to_db(payload.daily_carb_limit),
                decimal_to_db(payload.daily_protein_target),
                decimal_to_db(payload.daily_fat_target),
                current_user.user_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?;", (current_user.user_id,)
        ).fetchone()
        return UserProfileResponse(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            daily_carb_limit=db_to_decimal(row["daily_carb_limit"]),
            daily_protein_target=db_to_decimal(row["daily_protein_target"]),
            daily_fat_target=db_to_decimal(row["daily_fat_target"]),
        )


@app.get("/api/profile/banned", response_model=List[BannedIngredientResponse])
def list_banned_ingredients(current_user: CurrentUser = Depends(get_current_user)):
    with db_session() as conn:
        _ensure_user_exists(conn, current_user)
        rows = conn.execute(
            """
            SELECT b.id, b.user_id, b.ingredient_id, i.name AS ingredient_name
            FROM banned_ingredients b
            JOIN ingredients i ON i.id = b.ingredient_id
            WHERE b.user_id = ?
            ORDER BY i.name ASC;
            """,
            (current_user.user_id,),
        ).fetchall()
        return [
            BannedIngredientResponse(
                id=r["id"],
                user_id=r["user_id"],
                ingredient_id=r["ingredient_id"],
                ingredient_name=r["ingredient_name"],
            )
            for r in rows
        ]


@app.post(
    "/api/profile/banned",
    response_model=BannedIngredientResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_banned_ingredient(
    payload: BannedIngredientCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        _ensure_user_exists(conn, current_user)
        ing = conn.execute(
            "SELECT id, name FROM ingredients WHERE id = ?;",
            (payload.ingredient_id,),
        ).fetchone()
        if ing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Az alapanyag nem található.",
            )
        try:
            cursor = conn.execute(
                """
                INSERT INTO banned_ingredients (user_id, ingredient_id)
                VALUES (?, ?);
                """,
                (current_user.user_id, payload.ingredient_id),
            )
            ban_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT id FROM banned_ingredients WHERE user_id = ? AND ingredient_id = ?;",
                (current_user.user_id, payload.ingredient_id),
            ).fetchone()
            ban_id = int(existing["id"])

        return BannedIngredientResponse(
            id=ban_id,
            user_id=current_user.user_id,
            ingredient_id=ing["id"],
            ingredient_name=ing["name"],
        )


@app.delete(
    "/api/profile/banned/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_banned_ingredient(
    ingredient_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        conn.execute(
            "DELETE FROM banned_ingredients WHERE user_id = ? AND ingredient_id = ?;",
            (current_user.user_id, ingredient_id),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


@app.get("/api/recipes", response_model=List[RecipeResponse])
def list_recipes(
    search: Optional[str] = Query(default=None),
    _current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        if search:
            rows = conn.execute(
                "SELECT * FROM recipes WHERE LOWER(name) LIKE LOWER(?) ORDER BY id ASC;",
                (f"%{search}%",),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM recipes ORDER BY id ASC;").fetchall()
        return [_build_recipe_response(conn, r) for r in rows]


@app.post(
    "/api/recipes",
    response_model=RecipeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recipe(
    payload: RecipeCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        _ensure_user_exists(conn, current_user)
        # Verify all referenced ingredients exist
        for item in payload.items:
            ing = conn.execute(
                "SELECT id FROM ingredients WHERE id = ?;", (item.ingredient_id,)
            ).fetchone()
            if ing is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Az alapanyag (id={item.ingredient_id}) nem található.",
                )

        cursor = conn.execute(
            "INSERT INTO recipes (user_id, name, servings) VALUES (?, ?, ?);",
            (current_user.user_id, payload.name, decimal_to_db(payload.servings)),
        )
        recipe_id = int(cursor.lastrowid)

        for item in payload.items:
            conn.execute(
                "INSERT INTO recipe_items (recipe_id, ingredient_id, weight_g) VALUES (?, ?, ?);",
                (recipe_id, item.ingredient_id, decimal_to_db(item.weight_g)),
            )

        recipe_row = conn.execute(
            "SELECT * FROM recipes WHERE id = ?;", (recipe_id,)
        ).fetchone()
        return _build_recipe_response(conn, recipe_row)


# ---------------------------------------------------------------------------
# Daily logs & summary
# ---------------------------------------------------------------------------


@app.post(
    "/api/logs",
    response_model=DailyLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_daily_log(
    payload: DailyLogCreate,
    current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        _ensure_user_exists(conn, current_user)

        banned_rows = conn.execute(
            """
            SELECT b.ingredient_id, i.name
            FROM banned_ingredients b
            JOIN ingredients i ON i.id = b.ingredient_id
            WHERE b.user_id = ?;
            """,
            (current_user.user_id,),
        ).fetchall()
        banned_map = {r["ingredient_id"]: r["name"] for r in banned_rows}

        if payload.ingredient_id is not None:
            ing_row = conn.execute(
                "SELECT * FROM ingredients WHERE id = ?;", (payload.ingredient_id,)
            ).fetchone()
            if ing_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Az alapanyag nem található.",
                )
            if payload.ingredient_id in banned_map and payload.weight_g > Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Tiltólistás alapanyag nem naplózható: {banned_map[payload.ingredient_id]}.",
                )
            snapshot = calculate_item_macros(
                _row_to_macro_profile(ing_row), payload.weight_g
            )
            meal_name = payload.meal_name or ing_row["name"]
            weight_db = decimal_to_db(payload.weight_g)
            servings_db = None
        else:
            recipe_row = conn.execute(
                "SELECT * FROM recipes WHERE id = ?;", (payload.recipe_id,)
            ).fetchone()
            if recipe_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="A recept nem található.",
                )
            item_rows = conn.execute(
                """
                SELECT ri.ingredient_id, ri.weight_g, i.name,
                       i.energy_kcal, i.protein, i.carbs, i.sugar, i.fat,
                       i.saturated_fat, i.unsaturated_fat, i.fiber, i.salt
                FROM recipe_items ri
                JOIN ingredients i ON i.id = ri.ingredient_id
                WHERE ri.recipe_id = ?;
                """,
                (payload.recipe_id,),
            ).fetchall()

            banned_found = [
                banned_map[r["ingredient_id"]]
                for r in item_rows
                if r["ingredient_id"] in banned_map
                and db_to_decimal(r["weight_g"]) > Decimal("0.00")
            ]
            if banned_found:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Tiltólistás alapanyagot tartalmaz a recept: {', '.join(banned_found)}.",
                )

            recipe_servings = db_to_decimal(recipe_row["servings"])
            req_servings = payload.servings or Decimal("1.00")
            # Scale unrounded per ingredient, sum unrounded, multiply by req_servings / recipe_servings, round once
            unrounded_parts = [
                scale_macros_unrounded(
                    _row_to_macro_profile(r), db_to_decimal(r["weight_g"])
                )
                for r in item_rows
            ]
            ratio = req_servings / recipe_servings
            scaled_total = MacroProfile(
                energy_kcal=sum((p.energy_kcal for p in unrounded_parts), Decimal("0")) * ratio,
                protein=sum((p.protein for p in unrounded_parts), Decimal("0")) * ratio,
                carbs=sum((p.carbs for p in unrounded_parts), Decimal("0")) * ratio,
                sugar=sum((p.sugar for p in unrounded_parts), Decimal("0")) * ratio,
                fat=sum((p.fat for p in unrounded_parts), Decimal("0")) * ratio,
                saturated_fat=sum((p.saturated_fat for p in unrounded_parts), Decimal("0")) * ratio,
                unsaturated_fat=sum((p.unsaturated_fat for p in unrounded_parts), Decimal("0")) * ratio,
                fiber=sum((p.fiber for p in unrounded_parts), Decimal("0")) * ratio,
                salt=sum((p.salt for p in unrounded_parts), Decimal("0")) * ratio,
            )
            snapshot = scaled_total.rounded()
            meal_name = payload.meal_name or recipe_row["name"]
            weight_db = None
            servings_db = decimal_to_db(req_servings)

        cursor = conn.execute(
            """
            INSERT INTO daily_logs
                (user_id, log_date, meal_name, ingredient_id, recipe_id, weight_g, servings,
                 energy_kcal, protein, carbs, sugar, fat,
                 saturated_fat, unsaturated_fat, fiber, salt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                current_user.user_id,
                payload.log_date,
                meal_name,
                payload.ingredient_id,
                payload.recipe_id,
                weight_db,
                servings_db,
                decimal_to_db(snapshot.energy_kcal),
                decimal_to_db(snapshot.protein),
                decimal_to_db(snapshot.carbs),
                decimal_to_db(snapshot.sugar),
                decimal_to_db(snapshot.fat),
                decimal_to_db(snapshot.saturated_fat),
                decimal_to_db(snapshot.unsaturated_fat),
                decimal_to_db(snapshot.fiber),
                decimal_to_db(snapshot.salt),
            ),
        )

        return DailyLogResponse(
            id=int(cursor.lastrowid),
            user_id=current_user.user_id,
            log_date=payload.log_date,
            meal_name=meal_name,
            ingredient_id=payload.ingredient_id,
            recipe_id=payload.recipe_id,
            weight_g=payload.weight_g,
            servings=payload.servings,
            macros=_profile_to_snapshot(snapshot),
        )


@app.get("/api/logs/{log_date}", response_model=DailySummaryResponse)
def get_daily_summary(
    log_date: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    with db_session() as conn:
        user_row = _ensure_user_exists(conn, current_user)
        carb_limit = db_to_decimal(user_row["daily_carb_limit"])

        rows = conn.execute(
            """
            SELECT * FROM daily_logs
            WHERE user_id = ? AND log_date = ?
            ORDER BY id ASC;
            """,
            (current_user.user_id, log_date),
        ).fetchall()

        snapshots: list[MacroProfile] = []
        entries: list[DailyLogResponse] = []
        for r in rows:
            prof = _row_to_macro_profile(r)
            snapshots.append(prof)
            entries.append(
                DailyLogResponse(
                    id=r["id"],
                    user_id=r["user_id"],
                    log_date=r["log_date"],
                    meal_name=r["meal_name"],
                    ingredient_id=r["ingredient_id"],
                    recipe_id=r["recipe_id"],
                    weight_g=db_to_decimal(r["weight_g"]) if r["weight_g"] is not None else None,
                    servings=db_to_decimal(r["servings"]) if r["servings"] is not None else None,
                    macros=_profile_to_snapshot(prof),
                )
            )

        totals = sum_daily_snapshots(snapshots)
        day_status, remaining_carbs = evaluate_daily_carb_status(
            totals.carbs, carb_limit
        )

        return DailySummaryResponse(
            log_date=log_date,
            daily_carb_limit=carb_limit,
            remaining_carbs=remaining_carbs,
            status=day_status,
            totals=_profile_to_snapshot(totals),
            entries=entries,
        )


# ---------------------------------------------------------------------------
# Static Frontend (Vanilla HTML/CSS/JS)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
