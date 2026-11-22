# AGENTS.md – SmartMacro Fejlesztési Irányelvek

## Projekt kontextus
A SmartMacro egy Python (FastAPI) + SQLite + Vanilla HTML/JS alapú webes étrend- és makrotápanyag-követő alkalmazás.

## Kötelező működési szabályok (EU szabvány)
1. **Szénhidrát és cukor:** Az EU-s jelölést követjük. A `carbs` már a nettó (felszívódó) szénhidrát, a `fiber` külön tétel, a `sugar` pedig a `carbs` részhalmaza. TILOS a cukrot hozzáadni a szénhidráthoz, és TILOS a rostot levonni belőle. Érvényességi szabály: `0.00 <= sugar <= carbs`.
2. **Zsír és zsírsavak:** A `saturated_fat` és `unsaturated_fat` a `fat` részhalmazai. TILOS hozzáadni őket a zsírhoz. Érvényességi szabály: `0.00 <= saturated_fat + unsaturated_fat <= fat`.
3. **100 g-os korlát:** Alapanyag rögzítésekor `protein + carbs + fat + fiber + salt <= 100.00` (minden érték `>= 0.00`). Ennek megsértésekor `422 Unprocessable Entity` választ kell adni.
4. **Kerekítés és számábrázolás:**
   - TILOS `float` típust használni tápértékszámításhoz! Minden számítás `decimal.Decimal` típussal történjen.
   - Egy tételen/recepten belül az összetevőket kerekítés nélkül kell összegezni, és a tétel végeredményét `ROUND_HALF_UP` szabállyal `Decimal('0.01')` pontosságra kell kerekíteni.
   - A napi összesítés kizárólag a `daily_logs` táblában mentett, már kerekített snapshot értékeket adhatja össze.
5. **Tiltólista vs. kerettúllépés:**
   - Tiltólistás alapanyag (`> 0.00 g`) esetén a mentést `422` hibával el kell utasítani, megnevezve a tiltott alapanyagot.
   - Napi szénhidrátlimit túllépésekor (`> limit`, pl. `50.01 g` `50.00 g` limitnél) a mentés sikeres, de a napi státusz `KERET_TÚLLÉPVE`. Pontos elérésnél (`== limit`) még `MEGFELELŐ`.

## Kódolási és tesztelési elvárások
- Az üzleti/működési logika kizárólag a `backend/domain/` mappában lehet, adatbázistól függetlenül.
- Minden módosítás után futtasd a `pytest -v` parancsot.
- Minden új vagy módosított végponthoz kötelező automatizált tesztet írni a `tests/test_acceptance.py` fájlba.