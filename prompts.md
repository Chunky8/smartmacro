# SmartMacro – Fejlesztést irányító promptok

Az alábbiakban a SmartMacro alkalmazás fejlesztésének 8 fő tervezési és megvalósítási lépését irányító promptok találhatók, időrendi sorrendben.

---

## Prompt 1 – Domain réteg (`Decimal` kalkulátor, EU validátorok és unit tesztek)

> Olvasd el az `AGENTS.md` és a `docs/specifikacio.md` fájlokat.
> Hozd létre a `requirements.txt` fájlt (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`), valamint a `backend/domain/calculator.py` és `backend/domain/validators.py` modulokat.
>
> Követelmények:
> - Minden tápérték-számítás kizárólag `decimal.Decimal` típussal történjen, `float` használata tilos.
> - A `validators.py` ellenőrizze az EU-s szabályokat (`0.00 <= sugar <= carbs`, `0.00 <= saturated_fat + unsaturated_fat <= fat`, `protein + carbs + fat + fiber + salt <= 100.00`, negatív értékek tiltása, tömeg: `0.00 < weight_g <= 5000.00`).
> - A `calculator.py` valósítsa meg a 100 g-ról történő arányosítást: egy tételen/recepten belül kerekítés nélkül összegezzen, majd a tétel végeredményét `ROUND_HALF_UP` szabállyal `0.01` pontosságra kerekítse.
> - Írj unit teszteket a `tests/test_domain.py` fájlba, majd futtasd a `pytest -v` parancsot!

---

## Prompt 2 – Adatbázis (`sqlite3`), Pydantic sémák és jogosultságkezelés

> Készítsd el a `backend/database.py`, `backend/schemas.py` és `backend/auth.py` fájlokat az `AGENTS.md` alapján.
>
> Követelmények:
> - ORM (pl. SQLAlchemy) használata TILOS! Használd a Python beépített `sqlite3` modulját tiszta, paraméterezett SQL lekérdezésekkel (`?` placeholderekkel, SQL injection ellen védve).
> - A `database.py` hozza létre az SQLite táblákat (`CREATE TABLE IF NOT EXISTS`): `users`, `ingredients`, `banned_ingredients`, `recipes`, `recipe_items`, és `daily_logs` (utóbbi mentse el pillanatképként a számított `carbs`, `sugar`, `protein`, `fat`, `salt` értékeket).
> - A `Decimal` tápértékeket az SQLite-ban `TEXT` típusként tárold (pl. `"12.50"`), és lekérdezéskor alakítsd vissza `Decimal`-lá, hogy ne legyen lebegőpontos kerekítési hiba.
> - A `schemas.py` Pydantic modellei hívják meg a `domain/validators.py` szabályait, hogy hibás bemenetnél automatikusan `422 Unprocessable Entity` hiba menjen vissza.
> - Az `auth.py` valósítson meg egy egyszerű, fejlécalapú szerepkör-kezelést (`X-User-Id` és `X-User-Role`: `USER` vagy `ADMIN`), amely `403 Forbidden` hibát dob, ha nem `ADMIN` próbál törzsadatot módosítani.

---

## Prompt 3 – Kezdeti adatfeltöltés (`seed.py`) és FastAPI REST végpontok (`main.py`)

> Készítsd el a `backend/seed.py` és a `backend/main.py` fájlokat.
>
> 1. A `backend/seed.py` követelményei:
> - Ha az adatbázis üres, töltsön fel 1 alapértelmezett `USER` (50,00 g CH limit) és 1 `ADMIN` felhasználót.
> - Töltsön fel legalább **45–50 darab valós, változatos EU-s tápértékű alapanyagot** (húsok, halak, tojás, tejtermékek, zöldségek, olajok, magvak, fűszerek stb.). Minden egyes alapanyag feleljen meg szigorúan a `domain/validators.py` szabályainak!
> - Töltsön fel pontosan **100 darab változatos, életszerű receptet** (reggelik, ebédek, vacsorák, saláták, köretek) a fenti alapanyagokból összeállítva, valósághű tömegmennyiségekkel (`weight_g`) és adagszámokkal (`servings`).
>
> 2. A `backend/main.py` követelményei (FastAPI végpontok, sima SQL lekérdezésekkel):
> - Induláskor hívja meg a `seed.py` feltöltő függvényét, ha az adatbázis még üres.
> - `/api/ingredients` (`GET` mindenkinek; `POST`, `PUT`, `DELETE` csak `ADMIN`-nak)
> - `/api/profile` (`GET`, `PUT` a napi szénhidrátlimit és makrócélok kezelésére)
> - `/api/profile/banned` (`GET`, `POST`, `DELETE` a tiltólistához)
> - `/api/recipes` (`GET` opcionális név szerinti szűréssel, `POST`)
> - `/api/logs` (`POST` étkezés vagy recept naplózása: ellenőrizze a tiltólistát `422`-vel megnevezve a tiltott alapanyagot, számolja ki és mentse el a kerekített pillanatképet)
> - `/api/logs/{log_date}` (`GET` napi összesítő: csak a mentett snapshot tételeket adja össze, és számolja ki a státuszt: `MEGFELELŐ` vagy `KERET_TÚLLÉPVE`, valamint a maradék keretet).

---

## Prompt 4 – Izolált elfogadási tesztek (`conftest.py`, `test_acceptance.py`)

> Készítsd el a `tests/conftest.py` (ideiglenes/teszt SQLite adatbázis és FastAPI `TestClient`) és a `tests/test_acceptance.py` fájlokat.
>
> Követelmények:
> - A tesztek izolált, tiszta tesztadatbázison fussanak (ne keveredjenek a 100 induló recepttel), de írj egy külön tesztet arra is, hogy a `seed.py` hiba nélkül lefut, létrehozza a 100 receptet és az alapanyagokat, és minden feltöltött alapanyag átmegy a validáción.
> - A `test_acceptance.py` tartalmazzon külön, egyértelműen elnevezett tesztfüggvényeket a `docs/specifikacio.md` mind a 8 elfogadási feltételére (pl. `test_ac1_proportional_calculation_and_rounding`, `test_ac3_daily_limit_exact_and_exceeded` stb.), valamint egy külön tesztet a snapshot működésre (ha az admin módosít egy alapanyagot, a korábban mentett napi napló nem változik meg).
> - Futtasd le a `pytest -v` parancsot, és javítsd ki az esetleges hibákat, amíg minden teszt zöld nem lesz!

---

## Prompt 5 – Vanilla HTML/CSS/JS Frontend és statikus kiszolgálás

> Készítsd el a `frontend/index.html`, `frontend/style.css` és `frontend/app.js` fájlokat (tiszta HTML/CSS/Vanilla JS, keretrendszer nélkül), és szolgáld ki őket statikusan a `backend/main.py`-ből a `/` útvonalon.
>
> Követelmények:
> - A felső sávban legyen egy szerepkör-váltó (`Felhasználó` / `Adminisztrátor`), amely beállítja az `X-User-Role` fejlécet a `fetch` kérésekben.
> - Legyen 3 fül:
>   1. **Törzsadatok:** Alapanyagok táblázata (keresőmezővel a gyors szűréshez) és új alapanyag felvitele (adminként működjön, felhasználóként jelenítse meg a backendtől kapott `403` hibaüzenetet).
>   2. **Profil & Tiltólista:** Napi szénhidrátlimit beállítása és tiltólistás alapanyagok hozzáadása/törlése.
>   3. **Receptek & Napi Napló:** A 100 recept böngészése név szerinti keresővel és görgethető listával (mutatva az 1 adagra jutó makrókat), új recept összeállítása, étkezés/recept naplózása, valamint a napi egyenleg kijelzése jól látható `MEGFELELŐ` (zöld) vagy `KERET_TÚLLÉPVE` (piros) jelvénnyel.
> - Minden backendről érkező `422` vagy `403` hibaüzenetet jelenítsen meg a felületen egyértelműen.

---

## Prompt 6 – Elbukó vs. javított teszt dokumentálása (`docs/hiba_bemutatas.md`)

> A házi feladat kiírása szerint dokumentálnom kell legalább egy tesztről, hogy ismert hibás kódon elbukik, a javított változaton pedig átmegy (egyértelműen megjelölve, ha szándékosan előidézett hibáról van szó).
>
> Készíts egy `docs/hiba_bemutatas.md` fájlt, és mutassuk be a 3. elfogadási feltételen:
> 1. Hozz létre egy külön `tests/test_bug_demo.py` fájlt, amelyben látszik egy egyértelműen megjelölt, szándékosan hibás függvényváltozat (`<` operátor `<=` helyett a pontosan `50,00 g`-os határesetnél) és a valódi, javított változat.
> 2. Futtasd le a tesztet a hibás változaton, mentsd el a terminál kimenetét a `docs/hiba_bemutatas.md`-be, majd futtasd a javított változaton, és annak a kimenetét is dokumentáld ugyanott.

---

## Prompt 7 – Projekt dokumentáció (`README.md`)

> Írd meg a `README.md` fájlt magyarul a projekt gyökerébe. Tartalmazza az alábbiakat:
> 1. Rövid projektbemutató (említve az előre feltöltött EU-s alapanyag-adatbázist és a 100 receptet) és link a `docs/specifikacio.md` fájlra.
> 2. Pontos telepítési, indítási (`uvicorn backend.main:app --reload`) és tesztfuttatási (`pytest -v`) útmutató.
> 3. Az elfogadási feltételek (1–8.) és a hozzájuk tartozó automatizált tesztfüggvények megfeleltetési táblázata.
> 4. Egy külön szekció **„MI használat és dokumentált döntési esetek”** címmel, amelyben felsorolja a használt eszközöket (Gemini, Google Antigravity) és az `AGENTS.md` szerepét, valamint vázlatot ad a 3 kötelező döntési esethez (probléma, kontextus, MI javaslat, saját döntés és indoklás, ellenőrzési bizonyíték).

---

## Prompt 8 – Jelszavas hitelesítés, tokenes belépés és felhasználókezelés

> Módosítsd a SmartMacro alkalmazást (backend, adatbázis, seed, frontend, tesztek és `README.md`) jelszavas hitelesítéssel és felhasználókezeléssel az alábbi követelmények szerint:
>
> ### 1. Adatbázis és jelszókezelés (`backend/database.py`, `backend/auth.py`, `backend/schemas.py`)
> - A `users` táblát bővítsd ki `password_hash` oszloppal (`TEXT NOT NULL`), a `username` legyen egyedi (`UNIQUE`).
> - A jelszavakat ne sima szövegként, hanem a Python beépített `hashlib` moduljával (pl. SHA-256 vagy `pbkdf2_hmac`) hashelve tárold.
> - A korábbi puszta fejlécalapú (`X-User-Role`) szerepkörváltást cseréld le valódi tokenes bejelentkezésre (`Authorization: Bearer <token>`):
>   - `POST /api/auth/login`: fogadja a `username` és `password` mezőket, ellenőrizze a jelszó hash-t, hibás adatnál adjon `401 Unauthorized` választ, siker esetén adjon vissza egy session tokent (`secrets.token_hex`) és a felhasználó adatait (`id`, `username`, `role`).
>   - `POST /api/auth/logout`: érvénytelenítse a tokent.
>   - A védett végpontok a token alapján azonosítsák a felhasználót és a szerepkörét (`USER` vagy `ADMIN`). Ha `USER` próbál `ADMIN` végpontot hívni, továbbra is `403 Forbidden` választ adjon (8. elfogadási feltétel).
>
> ### 2. Új végpontok (`backend/main.py`)
> - `POST /api/users` (csak `ADMIN` jogosultsággal, különben `403 Forbidden`): új felhasználó létrehozása. Csak a `username` mezőt fogadja be, a szerepkör automatikusan `USER`, az alapértelmezett jelszó pedig `'basic'` legyen (hashelve mentve). Duplikált név esetén `409 Conflict` vagy `422` hibát adjon.
> - `GET /api/users` (csak `ADMIN` jogosultsággal): a regisztrált felhasználók listázása (`id`, `username`, `role` – jelszó hash nélkül).
> - `POST /api/auth/change-password` (bejelentkezett felhasználónak): fogadja a `old_password`, `new_password` és `confirm_password` mezőket. Ellenőrizze, hogy a régi jelszó helyes-e (különben `400`/`401` hiba), és hogy a két új jelszó megegyezik-e és nem üres (különben `422` hiba), majd frissítse a `password_hash` értéket az adatbázisban.
>
> ### 3. Kezdeti adatok módosítása (`backend/seed.py`)
> - Módosítsd a felhasználók inicializálását:
>   - 1 db `ADMIN` felhasználó: felhasználónév `admin`, jelszó `admin`.
>   - 3 db `USER` tesztfelhasználó: `'MakkMarci'`, `'RegősBendegúz'`, `'ToldiMiklós'`, mindegyikük alapértelmezett jelszava `'basic'` legyen (50,00 g napi CH limittel).
>
> ### 4. Frontend módosítása (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`)
> - **Bejelentkező képernyő:** Induláskor (ha nincs érvényes bejelentkezés) jelenjen meg egy tiszta jelszavas bejelentkező felület (felhasználónév + jelszó mező, hibaüzenet megjelenítése hibás belépéskor).
> - **Felhasználó váltása:** A felső sávban a korábbi szabad szerepkör-választó helyett jelenjen meg az aktuálisan bejelentkezett felhasználó neve, szerepköre, valamint egy **„Felhasználó váltása / Kijelentkezés”** gomb. Erre kattintva lépjen ki és hozza elő a jelszavas bejelentkező ablakot.
> - **Admin felhasználó-hozzáadás:** Ha `ADMIN` van bejelentkezve, jelenjen meg egy felhasználókezelő blokk (pl. az 1. fülön vagy külön admin szekcióban), ahol az admin kizárólag az új felhasználónevet megadva létrehozhat új felhasználót (jelezve a felületen, hogy az alapértelmezett jelszó: `basic`), és láthatja a meglévő felhasználók listáját.
> - **Jelszómódosítás a 2. fülön (Profil & Tiltólista):** Adj hozzá egy **„Jelszó módosítása”** dobozt 3 egymás alatti jelszómezővel: *Régi jelszó*, *Új jelszó*, *Új jelszó mégegyszer*, mentés gombbal és egyértelmű siker/hiba visszajelzéssel.
> - Minden API kérés küldje az `Authorization: Bearer <token>` fejlécet.
>
> ### 5. Tesztek és dokumentáció frissítése (`tests/`, `README.md`)
> - Frissítsd a `tests/conftest.py` és `tests/test_acceptance.py` fájlokat úgy, hogy a bejelentkezési tokent használják, és mind a 8 eredeti elfogadási feltétel továbbra is zöld legyen.
> - Adj hozzá új automatizált teszteket az alábbiakra:
>   - Sikeres és sikertelen bejelentkezés (`admin`/`admin`, illetve a 3 tesztfelhasználó `'basic'` jelszóval).
>   - Csak `ADMIN` hozhat létre új felhasználót (`USER` esetén `403`), és az új felhasználó be tud lépni a `'basic'` jelszóval.
>   - Sikeres jelszómódosítás, valamint hibás régi jelszó és eltérő új jelszavak elutasítása.
>   - A `seed.py` tesztje ellenőrizze a 3 tesztfelhasználó (`MakkMarci`, `RegősBendegúz`, `ToldiMiklós`) és az `admin` létrejöttét.
> - Frissítsd a `README.md` fájlt az új bejelentkezési működéssel, az alapértelmezett tesztfiókokkal (`admin` / `admin`; `MakkMarci`, `RegősBendegúz`, `ToldiMiklós` / `basic`), a jelszóváltoztatás és admin felhasználó-létrehozás leírásával, valamint a frissített tesztlistával.
> - Futtasd le a `pytest -v` parancsot, és győződj meg róla, hogy minden teszt hibátlanul átmegy!
