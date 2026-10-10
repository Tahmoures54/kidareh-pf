"""Versioned category, trade, and Iranian administrative-location catalogs."""
import json
from functools import lru_cache
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
