from decimal import Decimal, InvalidOperation
from typing import Union

ZERO = Decimal("0.00")
MAX_MACRO_SUM_PER_100G = Decimal("100.00")
MAX_WEIGHT_G = Decimal("5000.00")

NumericInput = Union[Decimal, int, str]


class DomainValidationError(ValueError):
    """Raised when a domain validation rule is violated."""


def ensure_decimal(value: NumericInput, field_name: str = "value") -> Decimal:
    """Ensure a value is a finite Decimal; explicitly forbids float and bool."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"A(z) '{field_name}' mező értéke nem lehet {type(value).__name__}; "
            "kizárólag Decimal (vagy int/str) engedélyezett."
        )
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, str)):
        try:
            dec = Decimal(str(value))
        except InvalidOperation as exc:
            raise DomainValidationError(
                f"A(z) '{field_name}' mező nem érvényes tizedes szám: {value!r}."
            ) from exc
    else:
        raise TypeError(
            f"A(z) '{field_name}' mező nem támogatott típusú: {type(value).__name__}."
        )

    if not dec.is_finite():
        raise DomainValidationError(
            f"A(z) '{field_name}' mező csak véges szám lehet."
        )
    return dec


def validate_non_negative(value: NumericInput, field_name: str) -> Decimal:
    dec = ensure_decimal(value, field_name)
    if dec < ZERO:
        raise DomainValidationError(
            f"A(z) '{field_name}' értéke nem lehet negatív ({dec})."
        )
    return dec


def validate_ingredient_macros(
    *,
    energy_kcal: NumericInput = ZERO,
    protein: NumericInput,
    carbs: NumericInput,
    sugar: NumericInput = ZERO,
    fat: NumericInput,
    saturated_fat: NumericInput = ZERO,
    unsaturated_fat: NumericInput = ZERO,
    fiber: NumericInput = ZERO,
    salt: NumericInput = ZERO,
) -> dict[str, Decimal]:
    """Validate EU nutrition labeling rules per 100 g of ingredient.

    Rules:
    - All values must be >= 0.00 (no floats allowed).
    - 0.00 <= sugar <= carbs
    - 0.00 <= saturated_fat + unsaturated_fat <= fat
    - protein + carbs + fat + fiber + salt <= 100.00
    """
    values = {
        "energy_kcal": validate_non_negative(energy_kcal, "energy_kcal"),
        "protein": validate_non_negative(protein, "protein"),
        "carbs": validate_non_negative(carbs, "carbs"),
        "sugar": validate_non_negative(sugar, "sugar"),
        "fat": validate_non_negative(fat, "fat"),
        "saturated_fat": validate_non_negative(saturated_fat, "saturated_fat"),
        "unsaturated_fat": validate_non_negative(unsaturated_fat, "unsaturated_fat"),
        "fiber": validate_non_negative(fiber, "fiber"),
        "salt": validate_non_negative(salt, "salt"),
    }

    if values["sugar"] > values["carbs"]:
        raise DomainValidationError(
            f"A cukortartalom ({values['sugar']} g) nem haladhatja meg "
            f"a szénhidráttartalmat ({values['carbs']} g)."
        )

    fatty_acids_sum = values["saturated_fat"] + values["unsaturated_fat"]
    if fatty_acids_sum > values["fat"]:
        raise DomainValidationError(
            f"A telített és telítetlen zsírsavak összege ({fatty_acids_sum} g) "
            f"nem haladhatja meg az összes zsírtartalmat ({values['fat']} g)."
        )

    macro_sum = (
        values["protein"]
        + values["carbs"]
        + values["fat"]
        + values["fiber"]
        + values["salt"]
    )
    if macro_sum > MAX_MACRO_SUM_PER_100G:
        raise DomainValidationError(
            f"A fő tápanyagok összege (fehérje + szénhidrát + zsír + rost + só = "
            f"{macro_sum} g) nem haladhatja meg a 100.00 g-ot."
        )

    return values


def validate_weight_g(weight_g: NumericInput) -> Decimal:
    """Validate ingredient weight in grams: 0.00 < weight_g <= 5000.00."""
    dec = ensure_decimal(weight_g, "weight_g")
    if dec <= ZERO or dec > MAX_WEIGHT_G:
        raise DomainValidationError(
            f"A tömegnek 0.00 g-nál nagyobbnak és legfeljebb 5000.00 g-nak kell lennie "
            f"(kapott érték: {dec} g)."
        )
    return dec


def validate_servings(servings: NumericInput) -> Decimal:
    """Validate recipe servings count: servings > 0."""
    dec = ensure_decimal(servings, "servings")
    if dec <= ZERO:
        raise DomainValidationError(
            f"Az adagszámnak 0-nál nagyobbnak kell lennie (kapott érték: {dec})."
        )
    return dec


def validate_daily_limit(limit: NumericInput, field_name: str = "carb_limit") -> Decimal:
    """Validate a daily macro limit: limit >= 0.00."""
    return validate_non_negative(limit, field_name)
