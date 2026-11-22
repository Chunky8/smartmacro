from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from backend.domain.validators import (
    DomainValidationError,
    ensure_decimal,
    validate_daily_limit,
    validate_servings,
    validate_weight_g,
)

QUANTIZE_2DP = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0.00")

STATUS_OK = "MEGFELELŐ"
STATUS_EXCEEDED = "KERET_TÚLLÉPVE"


def round_half_up(value: Decimal) -> Decimal:
    """Round a Decimal to 0.01 precision using ROUND_HALF_UP."""
    dec = ensure_decimal(value, "value")
    return dec.quantize(QUANTIZE_2DP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MacroProfile:
    """Nutrition profile expressed strictly in Decimal values (no floats)."""

    energy_kcal: Decimal = ZERO
    protein: Decimal = ZERO
    carbs: Decimal = ZERO
    sugar: Decimal = ZERO
    fat: Decimal = ZERO
    saturated_fat: Decimal = ZERO
    unsaturated_fat: Decimal = ZERO
    fiber: Decimal = ZERO
    salt: Decimal = ZERO

    def __post_init__(self) -> None:
        for field_name in (
            "energy_kcal",
            "protein",
            "carbs",
            "sugar",
            "fat",
            "saturated_fat",
            "unsaturated_fat",
            "fiber",
            "salt",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, Decimal):
                raise TypeError(
                    f"MacroProfile.{field_name} csak Decimal lehet, "
                    f"kapott típus: {type(val).__name__}."
                )

    def rounded(self) -> "MacroProfile":
        return MacroProfile(
            energy_kcal=round_half_up(self.energy_kcal),
            protein=round_half_up(self.protein),
            carbs=round_half_up(self.carbs),
            sugar=round_half_up(self.sugar),
            fat=round_half_up(self.fat),
            saturated_fat=round_half_up(self.saturated_fat),
            unsaturated_fat=round_half_up(self.unsaturated_fat),
            fiber=round_half_up(self.fiber),
            salt=round_half_up(self.salt),
        )


@dataclass(frozen=True)
class WeightedIngredient:
    """An ingredient's per-100g macro profile paired with a weight in grams."""

    macros_per_100g: MacroProfile
    weight_g: Decimal

    def __post_init__(self) -> None:
        validate_weight_g(self.weight_g)


def scale_macros_unrounded(
    macros_per_100g: MacroProfile, weight_g: Decimal
) -> MacroProfile:
    """Scale per-100g macros to weight_g WITHOUT intermediate rounding."""
    w = validate_weight_g(weight_g)
    return MacroProfile(
        energy_kcal=(macros_per_100g.energy_kcal * w) / HUNDRED,
        protein=(macros_per_100g.protein * w) / HUNDRED,
        carbs=(macros_per_100g.carbs * w) / HUNDRED,
        sugar=(macros_per_100g.sugar * w) / HUNDRED,
        fat=(macros_per_100g.fat * w) / HUNDRED,
        saturated_fat=(macros_per_100g.saturated_fat * w) / HUNDRED,
        unsaturated_fat=(macros_per_100g.unsaturated_fat * w) / HUNDRED,
        fiber=(macros_per_100g.fiber * w) / HUNDRED,
        salt=(macros_per_100g.salt * w) / HUNDRED,
    )


def calculate_item_macros(
    macros_per_100g: MacroProfile, weight_g: Decimal
) -> MacroProfile:
    """Calculate macros for a single weighted ingredient, rounded to 0.01 (ROUND_HALF_UP)."""
    return scale_macros_unrounded(macros_per_100g, weight_g).rounded()


def _sum_unrounded(profiles: Sequence[MacroProfile]) -> MacroProfile:
    return MacroProfile(
        energy_kcal=sum((p.energy_kcal for p in profiles), Decimal("0")),
        protein=sum((p.protein for p in profiles), Decimal("0")),
        carbs=sum((p.carbs for p in profiles), Decimal("0")),
        sugar=sum((p.sugar for p in profiles), Decimal("0")),
        fat=sum((p.fat for p in profiles), Decimal("0")),
        saturated_fat=sum((p.saturated_fat for p in profiles), Decimal("0")),
        unsaturated_fat=sum((p.unsaturated_fat for p in profiles), Decimal("0")),
        fiber=sum((p.fiber for p in profiles), Decimal("0")),
        salt=sum((p.salt for p in profiles), Decimal("0")),
    )


def calculate_composite_macros(items: Sequence[WeightedIngredient]) -> MacroProfile:
    """Sum unrounded scaled macros across all items in a recipe/meal, then round once to 0.01."""
    if not items:
        raise DomainValidationError("Legalább egy összetevő megadása kötelező.")
    unrounded_parts = [
        scale_macros_unrounded(item.macros_per_100g, item.weight_g) for item in items
    ]
    return _sum_unrounded(unrounded_parts).rounded()


def calculate_per_serving_macros(
    items: Sequence[WeightedIngredient], servings: Decimal
) -> MacroProfile:
    """Calculate per-serving macros: sum unrounded, divide by servings, then round once to 0.01."""
    if not items:
        raise DomainValidationError("Legalább egy összetevő megadása kötelező.")
    s = validate_servings(servings)
    unrounded_total = _sum_unrounded(
        [scale_macros_unrounded(item.macros_per_100g, item.weight_g) for item in items]
    )
    per_serving_unrounded = MacroProfile(
        energy_kcal=unrounded_total.energy_kcal / s,
        protein=unrounded_total.protein / s,
        carbs=unrounded_total.carbs / s,
        sugar=unrounded_total.sugar / s,
        fat=unrounded_total.fat / s,
        saturated_fat=unrounded_total.saturated_fat / s,
        unsaturated_fat=unrounded_total.unsaturated_fat / s,
        fiber=unrounded_total.fiber / s,
        salt=unrounded_total.salt / s,
    )
    return per_serving_unrounded.rounded()


def sum_daily_snapshots(snapshots: Sequence[MacroProfile]) -> MacroProfile:
    """Sum already-rounded daily log snapshots."""
    return _sum_unrounded(snapshots).rounded()


def evaluate_daily_carb_status(
    total_carbs: Decimal, carb_limit: Decimal
) -> tuple[str, Decimal]:
    """Return (status, remaining_carbs) for a daily carb total vs limit.

    Exact match (total_carbs == carb_limit) is still MEGFELELŐ.
    Exceeding (total_carbs > carb_limit) yields KERET_TÚLLÉPVE.
    """
    total = ensure_decimal(total_carbs, "total_carbs")
    limit = validate_daily_limit(carb_limit, "carb_limit")
    remaining = round_half_up(limit - total)
    status = STATUS_EXCEEDED if total > limit else STATUS_OK
    return status, remaining
