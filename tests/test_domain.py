from decimal import Decimal
import pytest

from backend.domain.calculator import (
    MacroProfile,
    STATUS_EXCEEDED,
    STATUS_OK,
    WeightedIngredient,
    calculate_composite_macros,
    calculate_item_macros,
    calculate_per_serving_macros,
    evaluate_daily_carb_status,
    round_half_up,
    sum_daily_snapshots,
)
from backend.domain.validators import (
    DomainValidationError,
    validate_ingredient_macros,
    validate_weight_g,
)


class TestValidators:
    def test_valid_ingredient_boundary_100g_and_max_subsets(self):
        result = validate_ingredient_macros(
            energy_kcal=Decimal("400.00"),
            protein=Decimal("20.00"),
            carbs=Decimal("30.00"),
            sugar=Decimal("30.00"),
            fat=Decimal("40.00"),
            saturated_fat=Decimal("15.00"),
            unsaturated_fat=Decimal("25.00"),
            fiber=Decimal("5.00"),
            salt=Decimal("5.00"),
        )
        assert result["carbs"] == Decimal("30.00")
        assert result["sugar"] == Decimal("30.00")
        assert result["fat"] == Decimal("40.00")

    def test_sugar_exceeds_carbs_raises(self):
        with pytest.raises(DomainValidationError, match="cukor"):
            validate_ingredient_macros(
                protein=Decimal("10.00"),
                carbs=Decimal("10.00"),
                sugar=Decimal("10.01"),
                fat=Decimal("5.00"),
            )

    def test_fatty_acids_exceed_fat_raises(self):
        with pytest.raises(DomainValidationError, match="zsírsavak"):
            validate_ingredient_macros(
                protein=Decimal("10.00"),
                carbs=Decimal("10.00"),
                fat=Decimal("10.00"),
                saturated_fat=Decimal("6.00"),
                unsaturated_fat=Decimal("4.01"),
            )

    def test_macro_sum_exceeds_100g_raises(self):
        with pytest.raises(DomainValidationError, match="100.00"):
            validate_ingredient_macros(
                protein=Decimal("30.00"),
                carbs=Decimal("30.00"),
                fat=Decimal("30.00"),
                fiber=Decimal("5.00"),
                salt=Decimal("5.01"),
            )

    def test_negative_value_raises(self):
        with pytest.raises(DomainValidationError, match="negatív"):
            validate_ingredient_macros(
                protein=Decimal("-0.01"),
                carbs=Decimal("10.00"),
                fat=Decimal("5.00"),
            )

    def test_float_is_forbidden_in_validator(self):
        with pytest.raises(TypeError):
            validate_ingredient_macros(
                protein=10.5,  # type: ignore[arg-type]
                carbs=Decimal("10.00"),
                fat=Decimal("5.00"),
            )

    @pytest.mark.parametrize(
        "weight",
        [Decimal("0.01"), Decimal("100.00"), Decimal("5000.00")],
    )
    def test_valid_weights(self, weight: Decimal):
        assert validate_weight_g(weight) == weight

    @pytest.mark.parametrize(
        "weight",
        [Decimal("0.00"), Decimal("-1.00"), Decimal("5000.01")],
    )
    def test_invalid_weights_raise(self, weight: Decimal):
        with pytest.raises(DomainValidationError):
            validate_weight_g(weight)

    def test_float_weight_raises_type_error(self):
        with pytest.raises(TypeError):
            validate_weight_g(100.0)  # type: ignore[arg-type]


class TestCalculator:
    def test_spec_acceptance_case_1_scaling_and_rounding(self):
        # 37 g of ingredient with 12.50 g carbs (4.00 g sugar) and 1.25 g salt per 100 g
        # carbs: 12.50 * 37 / 100 = 4.625 -> 4.63 (ROUND_HALF_UP)
        # sugar: 4.00 * 37 / 100 = 1.48
        # salt:  1.25 * 37 / 100 = 0.4625 -> 0.46
        macros = MacroProfile(
            carbs=Decimal("12.50"),
            sugar=Decimal("4.00"),
            salt=Decimal("1.25"),
        )
        result = calculate_item_macros(macros, Decimal("37"))
        assert result.carbs == Decimal("4.63")
        assert result.sugar == Decimal("1.48")
        assert result.salt == Decimal("0.46")

    def test_round_half_up_behavior(self):
        assert round_half_up(Decimal("0.005")) == Decimal("0.01")
        assert round_half_up(Decimal("0.015")) == Decimal("0.02")
        assert round_half_up(Decimal("4.625")) == Decimal("4.63")
        assert round_half_up(Decimal("0.4625")) == Decimal("0.46")

    def test_composite_sums_unrounded_before_final_rounding(self):
        # Each item: 1.00 g carbs/100g * 0.4 g = 0.004 g (would round to 0.00 individually)
        # Three items summed unrounded: 0.012 g -> rounds to 0.01 g
        ing = MacroProfile(carbs=Decimal("1.00"))
        items = [
            WeightedIngredient(ing, Decimal("0.4")),
            WeightedIngredient(ing, Decimal("0.4")),
            WeightedIngredient(ing, Decimal("0.4")),
        ]
        result = calculate_composite_macros(items)
        assert result.carbs == Decimal("0.01")

    def test_per_serving_calculation(self):
        ing = MacroProfile(protein=Decimal("25.00"), carbs=Decimal("10.00"))
        items = [WeightedIngredient(ing, Decimal("100.00"))]
        per_serving = calculate_per_serving_macros(items, Decimal("3"))
        # 25 / 3 = 8.3333... -> 8.33; 10 / 3 = 3.3333... -> 3.33
        assert per_serving.protein == Decimal("8.33")
        assert per_serving.carbs == Decimal("3.33")

    def test_daily_snapshot_summing_and_status(self):
        s1 = MacroProfile(carbs=Decimal("35.25"))
        s2 = MacroProfile(carbs=Decimal("14.75"))
        total = sum_daily_snapshots([s1, s2])
        assert total.carbs == Decimal("50.00")

        status_exact, remaining_exact = evaluate_daily_carb_status(
            total.carbs, Decimal("50.00")
        )
        assert status_exact == STATUS_OK
        assert remaining_exact == Decimal("0.00")

        status_over, remaining_over = evaluate_daily_carb_status(
            Decimal("50.01"), Decimal("50.00")
        )
        assert status_over == STATUS_EXCEEDED
        assert remaining_over == Decimal("-0.01")

    def test_macro_profile_rejects_float(self):
        with pytest.raises(TypeError):
            MacroProfile(carbs=12.5)  # type: ignore[arg-type]
