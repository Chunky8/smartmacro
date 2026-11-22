# SmartMacro – EU-szabványú Makrotápanyag- és Napi Étrend-optimalizáló

## 1. Projektbemutató

A **SmartMacro** egy Python (**FastAPI**) + beépített **SQLite** (ORM nélkül, paraméterezett SQL lekérdezésekkel) + **Vanilla HTML/CSS/JS** alapú webes étrend- és makrotápanyag-követő alkalmazás.

Főbb jellemzők:
- **Európai szabvány szerinti tápértékkezelés:** a szénhidrát nettó (felszívódó) érték, a cukor a szénhidrát részhalmaza (`0,00 <= cukor <= szénhidrát`), a telített és telítetlen zsírsavak a zsír részhalmazai (`0,00 <= telített + telítetlen <= zsír`), a fő tápanyagok összege pedig legfeljebb `100,00 g / 100 g`.
- **Századgramm (`0,01 g`) pontosság `float` nélkül:** minden számítás `decimal.Decimal` típussal történik (`ROUND_HALF_UP` kerekítéssel), az SQLite-ban `TEXT` formátumban tárolva a kerekítési hibák elkerüléséhez.
- **Előre feltöltött törzsadatbázis és receptgyűjtemény:** első induláskor a rendszer automatikusan feltölt **50 db valós, EU-s tápértékű alapanyagot** és pontosan **100 db változatos, életszerű receptet** (reggelik, ebédek, vacsorák, saláták, köretek).
- **Tiltólista és napi keretkövetés:** tiltólistás alapanyag naplózása `422` hibával elutasításra kerül, míg a napi szénhidrátlimit túllépésekor az étkezés elmentődik, a napi státusz pedig `KERET_TÚLLÉPVE` jelzésre vált.

Kapcsolódó dokumentációk:
- Részletes specifikáció és elfogadási feltételek: [docs/specifikacio.md](docs/specifikacio.md)
- Hibabemutatás (elbukó vs. javított teszt az AC3 határeseten): [docs/hiba_bemutatas.md](docs/hiba_bemutatas.md)
- Fejlesztési irányelvek: [AGENTS.md](AGENTS.md)

---

## 2. Telepítés, indítás és tesztelés

### Előfeltételek
- Python 3.12+

### Telepítés (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

*(Linux/macOS esetén aktiválás: `source .venv/bin/activate`)*

### Alkalmazás indítása
```powershell
uvicorn backend.main:app --reload
```

Indítás után a webes felület elérhető a böngészőben:
- **Frontend (SPA):** `http://127.0.0.1:8000/`
- **Swagger / OpenAPI dokumentáció:** `http://127.0.0.1:8000/docs`

### Automatizált tesztek futtatása
```powershell
pytest -v
```

---

## 3. Elfogadási feltételek és tesztek megfeleltetése

| # | Elfogadási feltétel (`docs/specifikacio.md`) | Automatizált tesztfüggvény (`tests/test_acceptance.py`) |
|---|---|---|
| **1.** | Arányosított tápértékszámítás és `ROUND_HALF_UP` kerekítés (`37 g` példa) | `test_ac1_proportional_calculation_and_rounding` |
| **2.** | Napi napló állapotfrissítése (`50,00 g` limit, `35,25 g` bevitel → `MEGFELELŐ`, `14,75 g` maradék) | `test_ac2_daily_log_status_and_remaining_carbs` |
| **3.** | Napi keret pontos elérése (`50,00 g` → `MEGFELELŐ`) és átlépése (`50,01 g` → `KERET_TÚLLÉPVE`) | `test_ac3_daily_limit_exact_and_exceeded` |
| **4.** | 100%-os makróösszeg (`100,00 g`) és maximális részhalmazok határesete | `test_ac4_boundary_100g_sum_and_max_subsets` |
| **5.** | Hibás makróarányok (`> 100,00 g`, `cukor > CH`, `telített + telítetlen > zsír`, negatív érték → `422`) | `test_ac5_invalid_macro_ratios_and_negative_values` |
| **6.** | Tiltólistás alapanyag szűrése közvetlen naplózásnál és receptben (`422` + alapanyag megnevezése) | `test_ac6_banned_ingredient_blocked_in_log_and_recipe` |
| **7.** | Érvénytelen tömegmennyiség (`<= 0,00 g` vagy `> 5000,00 g` → `422`) | `test_ac7_invalid_weight_rejected` |
| **8.** | Jogosulatlan művelet törzsadatokon (`USER` szerepkör → `403 Forbidden`) | `test_ac8_non_admin_forbidden_on_master_data` |
| **+** | Snapshot változatlansága törzsadat-módosítás után | `test_snapshot_immutability_after_ingredient_update` |
| **+** | Kezdeti adatfeltöltés (`50` validált alapanyag, `100` recept) | `test_seed_database_populates_100_recipes_and_valid_ingredients` |
| **+** | Statikus frontend kiszolgálás a `/` útvonalon | `test_frontend_static_root_served` |

További unit tesztek: `tests/test_domain.py` (domain validátorok és kalkulátor), valamint `tests/test_bug_demo.py` (AC3 hibabemutató).

---

## 4. MI használat és dokumentált döntési esetek

### Használt eszközök és munkafolyamat
- **MI eszközök:** **Gemini** és **Google Antigravity** (kódgenerálás, architektúra-tervezés, automatizált tesztírás és hibakeresés).
- **Az `AGENTS.md` szerepe:** A projekt gyökerében elhelyezett `AGENTS.md` rögzítette a kötelező EU-s tápértékszabályokat, a `float` tilalmát (`decimal.Decimal` kötelező használata), a `ROUND_HALF_UP` kerekítési elvet, a tiszta domain-réteg (`backend/domain/`) elkülönítését és a kötelező `pytest -v` tesztfuttatást. Ennek köszönhetően az MI minden lépésben egységes, ellenőrizhető szabályrendszer mentén generálta a kódot.

### Dokumentált döntési esetek

#### 1. döntési eset: Lebegőpontos (`float`) pontatlanság kiküszöbölése az adatbázisban és a számításokban
- **Probléma:** A tápértékek 100 g-ról történő arányosítása és összeadása bináris `float` típussal kerekítési eltéréseket okozhat (pl. `4,625` kerekítése vagy `0,1 + 0,2` eltérése), és az SQLite `REAL` típusa is lebegőpontos.
- **Kontextus:** A specifikáció `0,01 g` pontosságú, `ROUND_HALF_UP` kerekítést és a felületen látható számok pontos egyezését követeli meg.
- **MI javaslat:** Minden tápérték-számítás `decimal.Decimal` típussal történjen a `backend/domain/` rétegben (explicit `TypeError`-ral tiltva a `float`-ot), az SQLite táblákban pedig `TEXT` típusú oszlopokban tároljuk az értékeket (`decimal_to_db` / `db_to_decimal` konverzióval).
- **Saját döntés és indoklás:** A javaslatot elfogadtam, mert az SQLite nem rendelkezik natív `DECIMAL` típussal, így a `TEXT` + `Decimal` párosítás garantálja a veszteségmentes tárolást és a determinisztikus kerekítést.
- **Ellenőrzési bizonyíték:** `tests/test_domain.py` (`test_float_is_forbidden_in_validator`, `test_spec_acceptance_case_1_scaling_and_rounding`) és `tests/test_acceptance.py` (`test_ac1_proportional_calculation_and_rounding`) – mind zöld.

#### 2. döntési eset: EU-s részhalmaz-szabályok érvényesítése a seed és API rétegben
- **Probléma:** Az EU-s jelölésben a cukor a szénhidrát, a telített/telítetlen zsírsavak pedig a zsír részhalmazai; hibás adatoknál (pl. `telített + telítetlen > zsír`) a rendszernek `422` hibát kell adnia, ugyanakkor a 50 db előre feltöltött alapanyagnak is maradéktalanul meg kell felelnie ezeknek a szabályoknak.
- **Kontextus:** A tesztírás során a teszthelperek alapértelmezett zsírsavértékei (`1.00 + 3.00 = 4.00 g`) miatt az `AC2` és `AC3` tesztekben (ahol `fat = 2.00` illetve `0.00` volt) a saját EU-validátorunk `422` hibával elutasította a tesztalapanyag létrehozását.
- **MI javaslat:** A `backend/domain/validators.py` szabályai maradjanak szigorúak, a `seed.py` minden egyes alapanyagot futtasson át rajtuk, a teszthelper alapértelmezett zsírsavértékei pedig legyenek `0.00`.
- **Saját döntés és indoklás:** Elfogadtam a javaslatot: a domain validáció szigorúságán nem lazítottunk, hanem a tesztadatokat igazítottuk a valós EU-s szabályokhoz, ami egyben igazolta a validátor működését is.
- **Ellenőrzési bizonyíték:** `tests/test_acceptance.py` (`test_ac4_boundary_100g_sum_and_max_subsets`, `test_ac5_invalid_macro_ratios_and_negative_values`, `test_seed_database_populates_100_recipes_and_valid_ingredients`) – mind zöld.

#### 3. döntési eset: Napi napló pillanatképek (snapshot) és határeset-kezelés (`50,00 g` vs. `50,01 g`)
- **Probléma:** Ha egy adminisztrátor utólag módosít egy alapanyagot a törzsadatbázisban, a korábbi napok naplózott tápértékei nem változhatnak meg visszamenőleg; emellett pontosan `50,00 g` szénhidrátbevitel még `MEGFELELŐ`, csak `50,01 g`-tól `KERET_TÚLLÉPVE`.
- **Kontextus:** Kérdéses volt, hogy a napi összesítő dinamikusan számolja-e újra a makrókat az `ingredients` táblából, vagy tárolt pillanatképeket összegezzen.
- **MI javaslat:** A `daily_logs` tábla tárolja el a naplózáskor kerekített makró-pillanatképet (`carbs`, `sugar`, `protein`, `fat`, `salt` stb.), a `GET /api/logs/{log_date}` pedig kizárólag ezeket összegezze; a határesetet pedig szigorú `total > limit` feltétellel ellenőrizzük.
- **Saját döntés és indoklás:** A snapshot-alapú tárolás egyszerűbbé teszi a napi egyenleg konzisztenciáját és megvédi a múltbeli adatokat a törzsadat-módosításoktól. A határeset helyességét külön hibabemutató teszttel is igazoltuk (`docs/hiba_bemutatas.md`).
- **Ellenőrzési bizonyíték:** `tests/test_acceptance.py` (`test_ac3_daily_limit_exact_and_exceeded`, `test_snapshot_immutability_after_ingredient_update`) és `tests/test_bug_demo.py` – mind zöld (`31 passed, 1 xfailed`).
