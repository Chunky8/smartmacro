# Hiba bemutatása – 3. elfogadási feltétel (AC3 határeset)

> **Megjegyzés:** Az alábbi bemutatóban egy **szándékosan előidézett** (off-by-one / határeset) hibát mutatunk be a `tests/test_bug_demo.py` fájlban, hogy igazoljuk: a teszt valóban elkapja a hibás működést, a javított implementáción pedig átmegy.

## 1. A tesztelt követelmény (AC3)
A `docs/specifikacio.md` 3. elfogadási feltétele szerint `50,00 g`-os napi szénhidrátlimit esetén:
- pontosan `50,00 g` bevitelkor a státusz még **`MEGFELELŐ`** (`0,00 g` maradék keret),
- `50,01 g` bevitelkor a státusz **`KERET_TÚLLÉPVE`** (`-0,01 g` maradék keret).

## 2. A szándékosan hibás vs. javított kód

**Szándékosan hibás változat (`evaluate_daily_carb_status_BUGGY` a `tests/test_bug_demo.py`-ban):**
A feltétel `<` operátort használ `<=` helyett, így pontos egyezésnél (`50.00 == 50.00`) tévesen `KERET_TÚLLÉPVE` státuszt ad vissza:
```python
status = STATUS_OK if total_carbs < carb_limit else STATUS_EXCEEDED
```

**Valódi, javított változat (`evaluate_daily_carb_status` a `backend/domain/calculator.py`-ban):**
Csak szigorú túllépés (`total > limit`) esetén ad `KERET_TÚLLÉPVE` státuszt, pontos egyezésnél `MEGFELELŐ`:
```python
status = STATUS_EXCEEDED if total > limit else STATUS_OK
```

## 3. Futtatás a hibás változaton (elbukó teszt)

Parancs:
```powershell
.\.venv\Scripts\pytest.exe tests/test_bug_demo.py -v
```

Terminál kimenet:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\Oliver\Desktop\smartmacro\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Oliver\Desktop\smartmacro
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 2 items

tests/test_bug_demo.py::test_ac3_boundary_on_buggy_version FAILED        [ 50%]
tests/test_bug_demo.py::test_ac3_boundary_on_fixed_version PASSED        [100%]

================================== FAILURES ===================================
_____________________ test_ac3_boundary_on_buggy_version ______________________

    def test_ac3_boundary_on_buggy_version():
        """AC3 határeset tesztje a SZÁNDÉKOSAN HIBÁS függvényen (elbukik)."""
        status, remaining = evaluate_daily_carb_status_BUGGY(
            total_carbs=Decimal("50.00"),
            carb_limit=Decimal("50.00"),
        )
>       assert status == STATUS_OK
E       AssertionError: assert 'KERET_TÚLLÉPVE' == 'MEGFELELŐ'
E         
E         - MEGFELELŐ
E         + KERET_TÚLLÉPVE

tests\test_bug_demo.py:30: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_bug_demo.py::test_ac3_boundary_on_buggy_version - Assertion...
=================== 1 failed, 1 passed, 1 warning in 0.40s ====================
```

## 4. Futtatás a javított változaton (és a teljes tesztkészlet)

A szándékosan hibás demóteszt `@pytest.mark.xfail(strict=True)` jelöléssel szerepel a végleges repóban, így a teljes tesztcsomag igazolja mind a hibás változat bukását (`XFAIL`), mind a valódi `evaluate_daily_carb_status` függvény helyes működését (`PASSED`).

Parancs:
```powershell
.\.venv\Scripts\pytest.exe tests/test_bug_demo.py -v
```

Terminál kimenet:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\Oliver\Desktop\smartmacro\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Oliver\Desktop\smartmacro
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 2 items

tests/test_bug_demo.py::test_ac3_boundary_on_buggy_version XFAIL         [ 50%]
tests/test_bug_demo.py::test_ac3_boundary_on_fixed_version PASSED        [100%]

=================== 1 passed, 1 xfailed in 0.14s ==============================
```
