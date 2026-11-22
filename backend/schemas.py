from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.domain.validators import (
    validate_daily_limit,
    validate_ingredient_macros,
    validate_servings,
    validate_weight_g,
)


class MacroSnapshot(BaseModel):
    energy_kcal: Decimal = Decimal("0.00")
    protein: Decimal
    carbs: Decimal
    sugar: Decimal = Decimal("0.00")
    fat: Decimal
    saturated_fat: Decimal = Decimal("0.00")
    unsaturated_fat: Decimal = Decimal("0.00")
    fiber: Decimal = Decimal("0.00")
    salt: Decimal = Decimal("0.00")


class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    energy_kcal: Decimal = Decimal("0.00")
    protein: Decimal
    carbs: Decimal
    sugar: Decimal = Decimal("0.00")
    fat: Decimal
    saturated_fat: Decimal = Decimal("0.00")
    unsaturated_fat: Decimal = Decimal("0.00")
    fiber: Decimal = Decimal("0.00")
    salt: Decimal = Decimal("0.00")

    @model_validator(mode="after")
    def check_eu_rules(self) -> "IngredientCreate":
        validate_ingredient_macros(
            energy_kcal=self.energy_kcal,
            protein=self.protein,
            carbs=self.carbs,
            sugar=self.sugar,
            fat=self.fat,
            saturated_fat=self.saturated_fat,
            unsaturated_fat=self.unsaturated_fat,
            fiber=self.fiber,
            salt=self.salt,
        )
        return self


class IngredientUpdate(IngredientCreate):
    pass


class IngredientResponse(IngredientCreate):
    id: int
    is_verified: bool = True


class UserProfileUpdate(BaseModel):
    daily_carb_limit: Decimal
    daily_protein_target: Decimal = Decimal("100.00")
    daily_fat_target: Decimal = Decimal("70.00")

    @field_validator("daily_carb_limit")
    @classmethod
    def check_carb_limit(cls, v: Decimal) -> Decimal:
        return validate_daily_limit(v, "daily_carb_limit")

    @field_validator("daily_protein_target")
    @classmethod
    def check_protein_target(cls, v: Decimal) -> Decimal:
        return validate_daily_limit(v, "daily_protein_target")

    @field_validator("daily_fat_target")
    @classmethod
    def check_fat_target(cls, v: Decimal) -> Decimal:
        return validate_daily_limit(v, "daily_fat_target")


class UserProfileResponse(BaseModel):
    id: int
    username: str
    role: str
    daily_carb_limit: Decimal
    daily_protein_target: Decimal
    daily_fat_target: Decimal


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=128)


class UserSummary(BaseModel):
    id: int
    username: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserSummary


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def check_username_not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("A felhasználónév nem lehet üres.")
        return cleaned


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)
    confirm_password: str = Field(..., min_length=1, max_length=128)

    @model_validator(mode="after")
    def check_passwords_match(self) -> "ChangePasswordRequest":
        if not self.new_password.strip():
            raise ValueError("Az új jelszó nem lehet üres.")
        if self.new_password != self.confirm_password:
            raise ValueError("Az új jelszó és a megerősítés nem egyezik meg.")
        return self


class BannedIngredientCreate(BaseModel):
    ingredient_id: int = Field(..., ge=1)


class BannedIngredientResponse(BaseModel):
    id: int
    user_id: int
    ingredient_id: int
    ingredient_name: str


class RecipeItemCreate(BaseModel):
    ingredient_id: int = Field(..., ge=1)
    weight_g: Decimal

    @field_validator("weight_g")
    @classmethod
    def check_weight(cls, v: Decimal) -> Decimal:
        return validate_weight_g(v)


class RecipeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    servings: Decimal = Decimal("1.00")
    items: List[RecipeItemCreate] = Field(..., min_length=1)

    @field_validator("servings")
    @classmethod
    def check_servings(cls, v: Decimal) -> Decimal:
        return validate_servings(v)


class RecipeItemResponse(BaseModel):
    ingredient_id: int
    ingredient_name: str
    weight_g: Decimal


class RecipeResponse(BaseModel):
    id: int
    user_id: int
    name: str
    servings: Decimal
    items: List[RecipeItemResponse]
    total_macros: MacroSnapshot
    per_serving_macros: MacroSnapshot


class DailyLogCreate(BaseModel):
    log_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    meal_name: Optional[str] = Field(default=None, max_length=120)
    ingredient_id: Optional[int] = Field(default=None, ge=1)
    weight_g: Optional[Decimal] = None
    recipe_id: Optional[int] = Field(default=None, ge=1)
    servings: Optional[Decimal] = None

    @model_validator(mode="after")
    def check_source_and_quantities(self) -> "DailyLogCreate":
        has_ingredient = self.ingredient_id is not None
        has_recipe = self.recipe_id is not None
        if has_ingredient == has_recipe:
            raise ValueError(
                "Pontosan az egyiket kell megadni: vagy ingredient_id + weight_g, "
                "vagy recipe_id + servings."
            )
        if has_ingredient:
            if self.weight_g is None:
                raise ValueError("Alapanyag naplózásához a weight_g megadása kötelező.")
            validate_weight_g(self.weight_g)
        if has_recipe:
            if self.servings is None:
                self.servings = Decimal("1.00")
            validate_servings(self.servings)
        return self


class DailyLogResponse(BaseModel):
    id: int
    user_id: int
    log_date: str
    meal_name: str
    ingredient_id: Optional[int] = None
    recipe_id: Optional[int] = None
    weight_g: Optional[Decimal] = None
    servings: Optional[Decimal] = None
    macros: MacroSnapshot


class DailySummaryResponse(BaseModel):
    log_date: str
    daily_carb_limit: Decimal
    remaining_carbs: Decimal
    status: str
    totals: MacroSnapshot
    entries: List[DailyLogResponse]
