from decimal import Decimal
import pytest

from backend.domain.calculator import (
    STATUS_EXCEEDED,
    STATUS_OK,
    evaluate_daily_carb_status,
    round_half_up,
)


def evaluate_daily_carb_status_BUGGY(
    total_carbs: Decimal, carb_limit: Decimal
) -> tuple[str, Decimal]:
    """SZÁNDÉKOSAN HIBÁS változat (csak a hiba bemutatásához).

    Hiba: `<` operátort használ `<=` helyett (azaz pontosan 50.00 g == 50.00 g
    esetén már tévesen KERET_TÚLLÉPVE státuszt ad MEGFELELŐ helyett).
    """
    remaining = round_half_up(carb_limit - total_carbs)
    status = STATUS_OK if total_carbs < carb_limit else STATUS_EXCEEDED
    return status, remaining


@pytest.mark.xfail(
    strict=True,
    reason="Szándékosan hibás változat: a 50.00 g-os határesetet tévesen KERET_TÚLLÉPVE-nek minősíti.",
)
def test_ac3_boundary_on_buggy_version():
    """AC3 határeset tesztje a SZÁNDÉKOSAN HIBÁS függvényen (elbukik)."""
    status, remaining = evaluate_daily_carb_status_BUGGY(
        total_carbs=Decimal("50.00"),
        carb_limit=Decimal("50.00"),
    )
    assert status == STATUS_OK
    assert remaining == Decimal("0.00")


def test_ac3_boundary_on_fixed_version():
    """AC3 határeset tesztje a valódi, javított függvényen (átmegy)."""
    status_exact, remaining_exact = evaluate_daily_carb_status(
        total_carbs=Decimal("50.00"),
        carb_limit=Decimal("50.00"),
    )
    assert status_exact == STATUS_OK
    assert remaining_exact == Decimal("0.00")

    status_over, remaining_over = evaluate_daily_carb_status(
        total_carbs=Decimal("50.01"),
        carb_limit=Decimal("50.00"),
    )
    assert status_over == STATUS_EXCEEDED
    assert remaining_over == Decimal("-0.01")
