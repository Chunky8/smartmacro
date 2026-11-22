from decimal import Decimal
from typing import Optional

from backend.database import db_session, decimal_to_db
from backend.domain.validators import (
    validate_ingredient_macros,
    validate_servings,
    validate_weight_g,
)

# 50 realistic EU-labeled ingredients (per 100 g)
# Tuple format:
# (name, energy_kcal, protein, carbs, sugar, fat, saturated_fat, unsaturated_fat, fiber, salt)
SEED_INGREDIENTS: list[tuple[str, str, str, str, str, str, str, str, str, str]] = [
    # Húsok és baromfi
    ("Csirkemell filé", "110.00", "23.10", "0.00", "0.00", "1.20", "0.30", "0.70", "0.00", "0.15"),
    ("Csirkecomb filé (bőr nélkül)", "145.00", "19.50", "0.00", "0.00", "7.40", "2.10", "4.80", "0.00", "0.20"),
    ("Pulykamell filé", "108.00", "24.00", "0.00", "0.00", "1.00", "0.30", "0.50", "0.00", "0.15"),
    ("Marha hátszín", "185.00", "21.50", "0.00", "0.00", "11.00", "4.50", "5.80", "0.00", "0.18"),
    ("Sertés szűzpecsenye", "130.00", "21.00", "0.00", "0.00", "4.80", "1.70", "2.80", "0.00", "0.16"),
    ("Sertéskaraj", "165.00", "20.80", "0.00", "0.00", "8.90", "3.20", "5.10", "0.00", "0.18"),
    ("Bacon szalonna", "380.00", "14.00", "0.50", "0.50", "36.00", "13.00", "21.00", "0.00", "2.80"),
    ("Pulykasonka", "105.00", "18.50", "1.20", "0.80", "2.80", "0.90", "1.60", "0.00", "2.10"),
    # Halak és tenger gyümölcsei
    ("Lazacfilé", "208.00", "20.40", "0.00", "0.00", "13.40", "3.10", "9.20", "0.00", "0.12"),
    ("Tonhal (saját levében)", "112.00", "25.50", "0.00", "0.00", "1.00", "0.30", "0.50", "0.00", "0.95"),
    ("Tőkehal filé", "82.00", "18.00", "0.00", "0.00", "0.70", "0.15", "0.45", "0.00", "0.18"),
    ("Garnélarák", "95.00", "20.30", "0.20", "0.00", "1.10", "0.30", "0.60", "0.00", "0.80"),
    # Tojás és tejtermékek
    ("Tyúktojás", "143.00", "12.60", "0.70", "0.40", "9.50", "3.10", "5.50", "0.00", "0.35"),
    ("Tojásfehérje", "52.00", "10.90", "0.70", "0.70", "0.20", "0.00", "0.00", "0.00", "0.40"),
    ("Cottage cheese", "98.00", "12.50", "2.70", "2.50", "4.00", "2.50", "1.20", "0.00", "0.85"),
    ("Görög joghurt (10%)", "125.00", "6.20", "3.80", "3.80", "9.50", "6.20", "2.80", "0.00", "0.12"),
    ("Félzsíros tehéntúró", "135.00", "16.50", "3.50", "3.50", "6.00", "3.80", "1.80", "0.00", "0.10"),
    ("Mozzarella sajt", "265.00", "19.00", "1.00", "1.00", "20.50", "13.00", "6.50", "0.00", "0.70"),
    ("Cheddar sajt", "403.00", "25.00", "1.30", "0.50", "33.00", "21.00", "10.00", "0.00", "1.60"),
    ("Parmezán sajt", "415.00", "35.80", "0.90", "0.10", "29.00", "18.50", "9.00", "0.00", "1.80"),
    ("Feta sajt", "264.00", "14.20", "1.50", "1.50", "21.30", "14.90", "5.50", "0.00", "2.50"),
    ("Tejszín (30%)", "292.00", "2.20", "3.00", "3.00", "30.00", "19.50", "9.00", "0.00", "0.08"),
    ("Vaj (82%)", "740.00", "0.70", "0.60", "0.60", "82.00", "52.00", "26.00", "0.00", "0.05"),
    # Zöldségek
    ("Brokkoli", "34.00", "2.80", "4.00", "1.70", "0.40", "0.10", "0.20", "2.60", "0.08"),
    ("Karfiol", "25.00", "1.90", "3.00", "1.90", "0.30", "0.10", "0.15", "2.00", "0.07"),
    ("Spenót (friss)", "23.00", "2.90", "1.40", "0.40", "0.40", "0.10", "0.20", "2.20", "0.20"),
    ("Cukkini", "17.00", "1.20", "2.10", "1.80", "0.30", "0.10", "0.15", "1.00", "0.02"),
    ("Kígyóuborka", "15.00", "0.70", "2.20", "1.70", "0.10", "0.03", "0.05", "0.50", "0.01"),
    ("Paradicsom", "18.00", "0.90", "2.70", "2.60", "0.20", "0.05", "0.10", "1.20", "0.01"),
    ("Kaliforniai paprika", "31.00", "1.00", "4.60", "4.20", "0.30", "0.05", "0.15", "2.10", "0.01"),
    ("Csiperkegomba", "22.00", "3.10", "2.30", "1.90", "0.30", "0.05", "0.15", "1.00", "0.01"),
    ("Vöröshagyma", "40.00", "1.10", "7.60", "4.20", "0.10", "0.03", "0.05", "1.70", "0.01"),
    ("Fokhagyma", "149.00", "6.40", "30.90", "1.00", "0.50", "0.10", "0.30", "2.10", "0.04"),
    ("Avokádó", "160.00", "2.00", "1.80", "0.70", "14.70", "2.10", "11.60", "6.70", "0.02"),
    ("Jégsaláta", "14.00", "0.90", "1.80", "1.50", "0.10", "0.02", "0.05", "1.20", "0.02"),
    ("Rukkola", "25.00", "2.60", "2.10", "2.00", "0.70", "0.10", "0.45", "1.60", "0.07"),
    ("Zöldbab", "31.00", "1.80", "4.30", "3.30", "0.20", "0.05", "0.10", "2.70", "0.01"),
    ("Spárga", "20.00", "2.20", "1.80", "1.50", "0.10", "0.03", "0.05", "2.10", "0.01"),
    ("Padlizsán", "25.00", "1.00", "2.90", "2.50", "0.20", "0.04", "0.10", "3.00", "0.01"),
    ("Sárgarépa", "41.00", "0.90", "6.80", "4.70", "0.20", "0.04", "0.10", "2.80", "0.17"),
    # Gyümölcsök (alacsony CH)
    ("Málna", "52.00", "1.20", "5.40", "4.40", "0.70", "0.05", "0.45", "6.50", "0.01"),
    ("Áfonya", "57.00", "0.70", "12.10", "10.00", "0.30", "0.05", "0.20", "2.40", "0.01"),
    # Olajok, magvak, lisztek, fűszerek
    ("Extra szűz olívaolaj", "884.00", "0.00", "0.00", "0.00", "100.00", "14.00", "84.00", "0.00", "0.00"),
    ("Kókuszolaj", "890.00", "0.00", "0.00", "0.00", "100.00", "86.00", "10.00", "0.00", "0.00"),
    ("Mandula", "579.00", "21.20", "9.10", "4.40", "49.90", "3.80", "44.00", "12.50", "0.01"),
    ("Dió", "654.00", "15.20", "7.00", "2.60", "65.20", "6.10", "56.00", "6.70", "0.01"),
    ("Chia mag", "486.00", "16.50", "7.70", "0.00", "30.70", "3.30", "26.00", "34.40", "0.04"),
    ("Mandulaliszt", "590.00", "21.00", "9.00", "4.00", "52.00", "4.00", "45.00", "11.00", "0.02"),
    ("Tengeri só", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "99.50"),
    ("Fekete bors (őrölt)", "251.00", "10.40", "38.70", "0.60", "3.30", "1.40", "1.60", "25.30", "0.05"),
]


def _build_100_recipes() -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Build exactly 100 realistic Hungarian recipes using SEED_INGREDIENTS.

    Returns list of (recipe_name, servings, [(ingredient_name, weight_g), ...]).
    """
    recipes: list[tuple[str, str, list[tuple[str, str]]]] = []

    # 1. Reggelik (20 db)
    breakfast_bases = [
        ("Spenótos omlett mozzarellával", "1.00", [("Tyúktojás", "180.00"), ("Spenót (friss)", "60.00"), ("Mozzarella sajt", "40.00"), ("Vaj (82%)", "10.00"), ("Tengeri só", "1.00")]),
        ("Baconös rántotta", "1.00", [("Tyúktojás", "180.00"), ("Bacon szalonna", "50.00"), ("Vöröshagyma", "30.00"), ("Fekete bors (őrölt)", "1.00")]),
        ("Avokádós tükörtojás", "1.00", [("Tyúktojás", "120.00"), ("Avokádó", "80.00"), ("Extra szűz olívaolaj", "10.00"), ("Tengeri só", "1.00")]),
        ("Gombás cheddar omlett", "1.00", [("Tyúktojás", "180.00"), ("Csiperkegomba", "80.00"), ("Cheddar sajt", "35.00"), ("Vaj (82%)", "10.00")]),
        ("Cottage cheese tál uborkával", "1.00", [("Cottage cheese", "200.00"), ("Kígyóuborka", "100.00"), ("Kaliforniai paprika", "60.00"), ("Extra szűz olívaolaj", "5.00")]),
        ("Görög joghurtos málnás chia puding", "1.00", [("Görög joghurt (10%)", "150.00"), ("Chia mag", "25.00"), ("Málna", "60.00"), ("Mandula", "15.00")]),
        ("Áfonyás túrókrém dióval", "1.00", [("Félzsíros tehéntúró", "180.00"), ("Görög joghurt (10%)", "50.00"), ("Áfonya", "50.00"), ("Dió", "20.00")]),
        ("Pulykasonkás tojásfehérje omlett", "1.00", [("Tojásfehérje", "200.00"), ("Pulykasonka", "70.00"), ("Paradicsom", "80.00"), ("Extra szűz olívaolaj", "5.00")]),
        ("Füstölt lazacos avokádó tál", "1.00", [("Lazacfilé", "100.00"), ("Avokádó", "75.00"), ("Kígyóuborka", "80.00"), ("Rukkola", "30.00")]),
        ("Mandulalisztes keto palacsinta", "2.00", [("Mandulaliszt", "80.00"), ("Tyúktojás", "180.00"), ("Tejszín (30%)", "60.00"), ("Kókuszolaj", "15.00")]),
        ("Fetás cukkinis frittata", "2.00", [("Tyúktojás", "240.00"), ("Cukkini", "150.00"), ("Feta sajt", "70.00"), ("Extra szűz olívaolaj", "15.00")]),
        ("Brokkolis parmezános tojásmuffin", "2.00", [("Tyúktojás", "240.00"), ("Brokkoli", "120.00"), ("Parmezán sajt", "40.00"), ("Vaj (82%)", "10.00")]),
        ("Spárgás buggyantott tojás", "1.00", [("Tyúktojás", "120.00"), ("Spárga", "150.00"), ("Vaj (82%)", "15.00"), ("Parmezán sajt", "20.00")]),
        ("Paprikás pulykasonka tekercs sajttal", "1.00", [("Pulykasonka", "100.00"), ("Cheddar sajt", "40.00"), ("Kaliforniai paprika", "80.00"), ("Jégsaláta", "50.00")]),
        ("Kókuszolajos mandulás túrógolyó", "2.00", [("Félzsíros tehéntúró", "250.00"), ("Mandulaliszt", "40.00"), ("Kókuszolaj", "20.00"), ("Málna", "40.00")]),
        ("Tonhalas tojáskrém", "2.00", [("Tonhal (saját levében)", "140.00"), ("Tyúktojás", "120.00"), ("Görög joghurt (10%)", "60.00"), ("Vöröshagyma", "25.00")]),
        ("Paradicsomos mozzarella reggeli", "1.00", [("Mozzarella sajt", "125.00"), ("Paradicsom", "150.00"), ("Extra szűz olívaolaj", "15.00"), ("Rukkola", "30.00")]),
        ("Tejszínes lágy rántotta", "1.00", [("Tyúktojás", "180.00"), ("Tejszín (30%)", "40.00"), ("Vaj (82%)", "15.00"), ("Tengeri só", "1.00")]),
        ("Diós-málnás görög joghurt", "1.00", [("Görög joghurt (10%)", "200.00"), ("Dió", "25.00"), ("Málna", "70.00")]),
        ("Cottage cheese-es spenótos omlett", "1.00", [("Tyúktojás", "120.00"), ("Cottage cheese", "100.00"), ("Spenót (friss)", "50.00"), ("Vaj (82%)", "10.00")]),
    ]
    recipes.extend(breakfast_bases)

    # 2. Ebédek (25 db) - 5 fehérje × 5 köret/szósz kombináció
    lunch_proteins = [
        ("Grillezett csirkemell", "Csirkemell filé", "360.00"),
        ("Sült csirkecomb", "Csirkecomb filé (bőr nélkül)", "400.00"),
        ("Pulykamell steak", "Pulykamell filé", "360.00"),
        ("Sertés szűzérme", "Sertés szűzpecsenye", "360.00"),
        ("Marha hátszín", "Marha hátszín", "360.00"),
    ]
    lunch_styles = [
        ("fokhagymás brokkolival", [("Brokkoli", "300.00"), ("Fokhagyma", "10.00"), ("Extra szűz olívaolaj", "20.00"), ("Tengeri só", "2.00")]),
        ("tejszínes gombamártással", [("Csiperkegomba", "250.00"), ("Tejszín (30%)", "150.00"), ("Vöröshagyma", "60.00"), ("Vaj (82%)", "20.00")]),
        ("vajas karfiolpürével", [("Karfiol", "400.00"), ("Vaj (82%)", "30.00"), ("Parmezán sajt", "30.00"), ("Tengeri só", "2.00")]),
        ("zöldbabos parmezános raguval", [("Zöldbab", "300.00"), ("Parmezán sajt", "40.00"), ("Extra szűz olívaolaj", "20.00"), ("Fokhagyma", "8.00")]),
        ("baconös cukkiniágyon", [("Cukkini", "350.00"), ("Bacon szalonna", "60.00"), ("Kaliforniai paprika", "100.00"), ("Fekete bors (őrölt)", "2.00")]),
    ]
    for p_label, p_ing, p_w in lunch_proteins:
        for s_label, s_items in lunch_styles:
            recipes.append((f"{p_label} {s_label}", "2.00", [(p_ing, p_w)] + s_items))

    # 3. Vacsorák (25 db) - 5 hal/hús/sajt × 5 elkészítési mód
    dinner_proteins = [
        ("Sült lazacfilé", "Lazacfilé", "300.00"),
        ("Citromos tőkehal", "Tőkehal filé", "360.00"),
        ("Fokhagymás garnéla", "Garnélarák", "300.00"),
        ("Sertéskaraj szelet", "Sertéskaraj", "360.00"),
        ("Sült mozzarella és sonka", "Mozzarella sajt", "200.00"),
    ]
    dinner_styles = [
        ("spárgával és vajjal", [("Spárga", "250.00"), ("Vaj (82%)", "25.00"), ("Tengeri só", "2.00")]),
        ("spenótos tejszínes mártásban", [("Spenót (friss)", "180.00"), ("Tejszín (30%)", "120.00"), ("Fokhagyma", "10.00")]),
        ("grillezett padlizsánnal", [("Padlizsán", "300.00"), ("Extra szűz olívaolaj", "25.00"), ("Paradicsom", "120.00")]),
        ("avokádós rukkolával", [("Avokádó", "120.00"), ("Rukkola", "80.00"), ("Extra szűz olívaolaj", "15.00")]),
        ("cheddaros karfiol sütve", [("Karfiol", "320.00"), ("Cheddar sajt", "70.00"), ("Tejszín (30%)", "80.00")]),
    ]
    for p_label, p_ing, p_w in dinner_proteins:
        for s_label, s_items in dinner_styles:
            recipes.append((f"{p_label} {s_label}", "2.00", [(p_ing, p_w)] + s_items))

    # 4. Saláták (15 db)
    salads = [
        ("Görög saláta fetával", "2.00", [("Kígyóuborka", "200.00"), ("Paradicsom", "200.00"), ("Feta sajt", "120.00"), ("Kaliforniai paprika", "100.00"), ("Extra szűz olívaolaj", "25.00")]),
        ("Csirkés cézár stílusú saláta", "2.00", [("Csirkemell filé", "250.00"), ("Jégsaláta", "200.00"), ("Parmezán sajt", "40.00"), ("Extra szűz olívaolaj", "20.00")]),
        ("Tonhalas avokádó saláta", "2.00", [("Tonhal (saját levében)", "200.00"), ("Avokádó", "140.00"), ("Kígyóuborka", "150.00"), ("Rukkola", "60.00"), ("Extra szűz olívaolaj", "15.00")]),
        ("Lazacos spenótsaláta", "2.00", [("Lazacfilé", "220.00"), ("Spenót (friss)", "120.00"), ("Avokádó", "100.00"), ("Mandula", "25.00")]),
        ("Garnélás rukkola saláta", "2.00", [("Garnélarák", "220.00"), ("Rukkola", "100.00"), ("Paradicsom", "150.00"), ("Extra szűz olívaolaj", "20.00")]),
        ("Caprese mozzarella saláta", "2.00", [("Mozzarella sajt", "200.00"), ("Paradicsom", "250.00"), ("Extra szűz olívaolaj", "20.00"), ("Tengeri só", "2.00")]),
        ("Pulykás diós saláta", "2.00", [("Pulykamell filé", "240.00"), ("Jégsaláta", "180.00"), ("Dió", "30.00"), ("Cheddar sajt", "50.00"), ("Extra szűz olívaolaj", "15.00")]),
        ("Tojásos baconös kerti saláta", "2.00", [("Tyúktojás", "180.00"), ("Bacon szalonna", "60.00"), ("Jégsaláta", "180.00"), ("Paradicsom", "120.00")]),
        ("Fetás brokkoli saláta", "2.00", [("Brokkoli", "280.00"), ("Feta sajt", "100.00"), ("Mandula", "30.00"), ("Extra szűz olívaolaj", "20.00")]),
        ("Cottage cheese-es tavaszi saláta", "2.00", [("Cottage cheese", "250.00"), ("Kígyóuborka", "160.00"), ("Kaliforniai paprika", "120.00"), ("Rukkola", "60.00")]),
        ("Marhahúsos zöldsaláta", "2.00", [("Marha hátszín", "240.00"), ("Rukkola", "100.00"), ("Parmezán sajt", "35.00"), ("Extra szűz olívaolaj", "20.00")]),
        ("Sárgarépás mandulás ropogós saláta", "2.00", [("Sárgarépa", "150.00"), ("Jégsaláta", "180.00"), ("Mandula", "30.00"), ("Görög joghurt (10%)", "80.00")]),
        ("Spárgás tojássaláta", "2.00", [("Spárga", "220.00"), ("Tyúktojás", "180.00"), ("Görög joghurt (10%)", "70.00"), ("Extra szűz olívaolaj", "15.00")]),
        ("Gombás spenótsaláta parmezánnal", "2.00", [("Csiperkegomba", "180.00"), ("Spenót (friss)", "120.00"), ("Parmezán sajt", "40.00"), ("Extra szűz olívaolaj", "20.00")]),
        ("Avokádós cukkinisaláta fetával", "2.00", [("Cukkini", "220.00"), ("Avokádó", "120.00"), ("Feta sajt", "90.00"), ("Extra szűz olívaolaj", "15.00")]),
    ]
    recipes.extend(salads)

    # 5. Köretek és snackek (15 db)
    sides = [
        ("Vajas karfiolrizs", "2.00", [("Karfiol", "350.00"), ("Vaj (82%)", "25.00"), ("Tengeri só", "2.00")]),
        ("Fokhagymás párolt brokkoli", "2.00", [("Brokkoli", "350.00"), ("Fokhagyma", "10.00"), ("Extra szűz olívaolaj", "20.00")]),
        ("Grillezett cukkini szeletek", "2.00", [("Cukkini", "350.00"), ("Extra szűz olívaolaj", "20.00"), ("Fokhagyma", "8.00"), ("Tengeri só", "2.00")]),
        ("Parmezános sült spárga", "2.00", [("Spárga", "300.00"), ("Parmezán sajt", "35.00"), ("Extra szűz olívaolaj", "15.00")]),
        ("Fokhagymás pirított zöldbab", "2.00", [("Zöldbab", "320.00"), ("Vaj (82%)", "20.00"), ("Fokhagyma", "10.00")]),
        ("Tejszínes spenótfőzelék", "2.00", [("Spenót (friss)", "300.00"), ("Tejszín (30%)", "120.00"), ("Fokhagyma", "10.00"), ("Vaj (82%)", "15.00")]),
        ("Sült padlizsánkrém", "3.00", [("Padlizsán", "450.00"), ("Extra szűz olívaolaj", "35.00"), ("Vöröshagyma", "40.00"), ("Fokhagyma", "10.00")]),
        ("Vajas pirított csiperkegomba", "2.00", [("Csiperkegomba", "320.00"), ("Vaj (82%)", "25.00"), ("Fekete bors (őrölt)", "2.00")]),
        ("Cheddaros karfiolpüré", "2.00", [("Karfiol", "380.00"), ("Cheddar sajt", "60.00"), ("Vaj (82%)", "20.00")]),
        ("Sült kaliforniai paprika olívaolajjal", "2.00", [("Kaliforniai paprika", "300.00"), ("Extra szűz olívaolaj", "20.00"), ("Fokhagyma", "8.00")]),
        ("Guacamole avokádókrém", "2.00", [("Avokádó", "200.00"), ("Paradicsom", "80.00"), ("Vöröshagyma", "30.00"), ("Tengeri só", "2.00")]),
        ("Mandulás-sárgarépás párolt zöldség", "2.00", [("Sárgarépa", "200.00"), ("Brokkoli", "200.00"), ("Mandula", "25.00"), ("Vaj (82%)", "15.00")]),
        ("Kókuszolajos pirított mandula", "2.00", [("Mandula", "100.00"), ("Kókuszolaj", "10.00"), ("Tengeri só", "2.00")]),
        ("Körözött félzsíros túróból", "2.00", [("Félzsíros tehéntúró", "250.00"), ("Görög joghurt (10%)", "80.00"), ("Vöröshagyma", "30.00"), ("Tengeri só", "2.00")]),
        ("Mandulalisztes sajtos tallér", "3.00", [("Mandulaliszt", "120.00"), ("Cheddar sajt", "100.00"), ("Tyúktojás", "60.00"), ("Vaj (82%)", "30.00")]),
    ]
    recipes.extend(sides)

    assert len(recipes) == 100, f"Expected 100 recipes, got {len(recipes)}"
    return recipes


def seed_database(db_path: Optional[str] = None) -> None:
    """Populate initial users, 50 EU-validated ingredients, and 100 recipes if DB is empty."""
    with db_session(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM ingredients;").fetchone()[0]
        if count > 0:
            return

        # Default USER (id=1, 50.00 g CH limit) and ADMIN (id=2)
        conn.execute(
            """
            INSERT OR REPLACE INTO users
                (id, username, role, daily_carb_limit, daily_protein_target, daily_fat_target)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (1, "user", "USER", "50.00", "120.00", "70.00"),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO users
                (id, username, role, daily_carb_limit, daily_protein_target, daily_fat_target)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (2, "admin", "ADMIN", "50.00", "120.00", "70.00"),
        )

        # Insert 50 validated ingredients
        ingredient_id_by_name: dict[str, int] = {}
        for (
            name,
            energy_kcal,
            protein,
            carbs,
            sugar,
            fat,
            saturated_fat,
            unsaturated_fat,
            fiber,
            salt,
        ) in SEED_INGREDIENTS:
            validated = validate_ingredient_macros(
                energy_kcal=Decimal(energy_kcal),
                protein=Decimal(protein),
                carbs=Decimal(carbs),
                sugar=Decimal(sugar),
                fat=Decimal(fat),
                saturated_fat=Decimal(saturated_fat),
                unsaturated_fat=Decimal(unsaturated_fat),
                fiber=Decimal(fiber),
                salt=Decimal(salt),
            )
            cursor = conn.execute(
                """
                INSERT INTO ingredients
                    (name, energy_kcal, protein, carbs, sugar, fat,
                     saturated_fat, unsaturated_fat, fiber, salt, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    name,
                    decimal_to_db(validated["energy_kcal"]),
                    decimal_to_db(validated["protein"]),
                    decimal_to_db(validated["carbs"]),
                    decimal_to_db(validated["sugar"]),
                    decimal_to_db(validated["fat"]),
                    decimal_to_db(validated["saturated_fat"]),
                    decimal_to_db(validated["unsaturated_fat"]),
                    decimal_to_db(validated["fiber"]),
                    decimal_to_db(validated["salt"]),
                    1,
                ),
            )
            ingredient_id_by_name[name] = int(cursor.lastrowid)

        # Insert exactly 100 recipes
        for recipe_name, servings_str, items in _build_100_recipes():
            servings = validate_servings(Decimal(servings_str))
            cursor = conn.execute(
                """
                INSERT INTO recipes (user_id, name, servings)
                VALUES (?, ?, ?);
                """,
                (1, recipe_name, decimal_to_db(servings)),
            )
            recipe_id = int(cursor.lastrowid)
            for ing_name, weight_str in items:
                weight = validate_weight_g(Decimal(weight_str))
                ing_id = ingredient_id_by_name[ing_name]
                conn.execute(
                    """
                    INSERT INTO recipe_items (recipe_id, ingredient_id, weight_g)
                    VALUES (?, ?, ?);
                    """,
                    (recipe_id, ing_id, decimal_to_db(weight)),
                )
