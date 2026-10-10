"""Versioned category, trade, and Iranian administrative-location catalogs."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


def _load(name):
    with (DATA_DIR / name).open("r", encoding="utf-8") as source:
        return json.load(source)


CATEGORY_TREE = _load("categories.json")
IRAN_LOCATIONS = _load("iran_locations.json")
TRADE_GROUPS = _load("trades.json")


def normalize_location_name(value):
    """Normalize Persian/Arabic letter variants and whitespace for city matching."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().replace("ي", "ی").replace("ك", "ک").split())


# Only entries in the administrative cities catalog are valid city selections.
# Villages are intentionally excluded and are searchable only via kind=village.
CITY_NAMES = {
    normalize_location_name(item.get("name", ""))
    for item in IRAN_LOCATIONS.get("cities", [])
    if item.get("name")
}


def is_city_name(value):
    """Return whether a value matches a city in the canonical Iranian directory."""
    return normalize_location_name(value) in CITY_NAMES


# --- Location search index ---------------------------------------------------
# The city picker queries this catalogue on every keystroke, so entries are
# normalized once at import time instead of per request. `iran_locations.json`
# stays the single source of truth; this is only a pre-computed view of it.
LOCATION_TYPE_RANK = {"city": 0, "urban_zone": 1, "important_point": 2, "province_capital": 3}

# Offered when the picker opens with an empty query.
POPULAR_CITY_NAMES = (
    "تهران", "مشهد", "اصفهان", "کرج", "شیراز", "تبریز", "قم",
    "اهواز", "کرمانشاه", "رشت", "کرمان", "یزد", "ساری", "بندرعباس", "اراک",
)


def _build_location_index() -> dict[str, list[tuple[str, dict]]]:
    provinces = {item["id"]: item["name"] for item in IRAN_LOCATIONS["provinces"]}
    counties = {item["id"]: item["name"] for item in IRAN_LOCATIONS["counties"]}

    def entry(name, identifier, kind, province="", county="", extra=None):
        payload = {
            "id": identifier,
            "name": name,
            "type": kind,
            "province": province,
            "county": county,
        }
        if extra:
            payload.update(extra)
        return (normalize_location_name(name), payload)

    cities: list[tuple[str, dict]] = []
    for item in IRAN_LOCATIONS["cities"]:
        cities.append(
            entry(
                item["name"],
                item["id"],
                "city",
                provinces.get(item["province_id"], ""),
                counties.get(item["county_id"], ""),
            )
        )
    for item in IRAN_LOCATIONS.get("urban_zones", []):
        cities.append(
            entry(
                item["name"],
                item["id"],
                "urban_zone",
                provinces.get(item["province_id"], ""),
                counties.get(item["county_id"], ""),
                {"parent_city_id": item.get("city_id")},
            )
        )

    points: list[tuple[str, dict]] = []
    for item in IRAN_LOCATIONS.get("county_centers", []):
        # County centres are searchable as places and selectable as map points.
        cities.append(
            entry(
                item["center_name"],
                item["county_id"],
                "important_point",
                provinces.get(item["province_id"], ""),
                item["county_name"],
            )
        )
        points.append(
            entry(
                item["center_name"],
                item["county_id"],
                "important_point",
                provinces.get(item["province_id"], ""),
                item["county_name"],
                {"latitude": item.get("latitude"), "longitude": item.get("longitude")},
            )
        )
    for item in IRAN_LOCATIONS.get("province_capitals", []):
        points.append(
            entry(
                item["center_name"],
                item["province_id"],
                "province_capital",
                item["province_name"],
                "",
                {"latitude": item.get("latitude"), "longitude": item.get("longitude")},
            )
        )

    return {"city": cities, "point": points}


LOCATION_INDEX = _build_location_index()

# Only genuine cities, so the "popular cities" shortcut cannot resolve to an
# urban zone or county centre that happens to share a name.
CITY_INDEX_BY_NAME = {
    normalized: payload
    for normalized, payload in LOCATION_INDEX["city"]
    if payload["type"] == "city"
}
POPULAR_CITIES = [
    CITY_INDEX_BY_NAME[normalize_location_name(name)]
    for name in POPULAR_CITY_NAMES
    if normalize_location_name(name) in CITY_INDEX_BY_NAME
]


CATEGORIES = [
    {"id": group["id"], "name": group["group"], "icon": group.get("icon", "▦"),
     "description": group.get("description", ""), "types": group.get("types", [])}
    for group in CATEGORY_TREE
]
CATEGORY_GROUPS = {group["id"]: [item["value"] for item in group["types"]] for group in CATEGORY_TREE}
CATEGORY_LABELS = {group["id"]: group["group"] for group in CATEGORY_TREE}
for group in CATEGORY_TREE:
    for item in group["types"]:
        CATEGORY_LABELS[item["value"]] = item["text"]

# Keep legacy listing IDs valid so existing demo data and already-published listings remain searchable.
LEGACY_CATEGORY_GROUPS = {
    "home": ("home_and_life", "home_appliances_group"),
    "digital": ("digital_goods",),
    "fashion": ("personal_goods", "beauty_care"),
    "vehicle": ("vehicles",),
    "services": ("jobs",),
    "other": ("others",),
}
LEGACY_CATEGORY_NAMES = {
    "home": "خانه و زندگی", "digital": "دیجیتال", "fashion": "پوشاک",
    "vehicle": "خودرو", "services": "خدمات", "other": "سایر",
}
CATEGORY_ALLOWED_IDS = set(CATEGORY_LABELS) | set(LEGACY_CATEGORY_NAMES)
CATEGORY_ALLOWED_IDS.update(CATEGORY_GROUPS)
for legacy_id, groups in LEGACY_CATEGORY_GROUPS.items():
    CATEGORY_LABELS[legacy_id] = LEGACY_CATEGORY_NAMES[legacy_id]
    for group_id in groups:
        CATEGORY_GROUPS.setdefault(legacy_id, [])
        CATEGORY_GROUPS[legacy_id].extend(CATEGORY_GROUPS.get(group_id, []))
        CATEGORY_GROUPS.setdefault(group_id, []).append(legacy_id)
