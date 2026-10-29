# -*- coding: utf-8 -*-
"""Аренда квартир и домов в Holýšov с Sreality.cz (их JSON API)."""
import logging
import time

import config
from util import norm, contains_word, haversine_km

log = logging.getLogger(__name__)

API = "https://www.sreality.cz/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HolysovBot/1.0 (personal use)",
    "Accept": "application/json",
}
PER_PAGE = 60
MAX_PAGES = 15
MAIN_SLUG = {1: "byt", 2: "dum"}

_locality_cache = None


def resolve_locality(session):
    global _locality_cache
    if _locality_cache:
        return _locality_cache
    try:
        r = session.get(f"{API}/localities/suggest", params={"phrase": config.HOUSING_TOWN, "limit": 10},
                        headers=HEADERS, timeout=30)
        r.raise_for_status()
        for d in r.json().get("results", []):
            ud = d.get("userData") or {}
            name = ud.get("suggestFirstRow") or ud.get("municipality") or ""
            if ud.get("entityType") == "municipality" and norm(name) == norm(config.HOUSING_TOWN) \
                    and ud.get("district_id"):
                _locality_cache = [{"locality_district_id": ud["district_id"]}]
                log.info("Sreality: %s -> district_id %s", name, ud["district_id"])
                return _locality_cache
    except Exception as e:
        log.warning("Sreality suggest не сработал: %s", e)
    log.warning("Использую запасной фильтр по краю %s", config.SREALITY_REGION_FALLBACK)
    return [{"locality_region_id": rid} for rid in config.SREALITY_REGION_FALLBACK]


def in_town(estate: dict) -> bool:
    loc = estate.get("locality") or {}
    for key in ("city", "citypart", "municipality"):
        if contains_word(loc.get(key), config.HOUSING_TOWN):
            return True
    lat, lon = loc.get("gps_lat"), loc.get("gps_lon")
    if lat and lon:
        return haversine_km(config.HOUSING_CENTER, (lat, lon)) <= config.HOUSING_RADIUS_KM
    return False


def detail_url(e: dict) -> str:
    main = MAIN_SLUG.get((e.get("category_main_cb") or {}).get("value"), "byt")
    sub = norm((e.get("category_sub_cb") or {}).get("name")).replace(" ", "-") or "x"
    loc = (e.get("locality") or {}).get("city_seo_name") or "x"
    return f"https://www.sreality.cz/detail/pronajem/{main}/{sub}/{loc}/{e['hash_id']}"


def compact(e: dict) -> dict:
    loc = e.get("locality") or {}
    where = ", ".join(p for p in (loc.get("street"), loc.get("citypart") or loc.get("city")) if p)
    return {
        "id": str(e["hash_id"]),
        "title": (e.get("advert_name") or "Pronájem").replace("\xa0", " "),
        "locality": where,
        "price": e.get("price_czk") or e.get("price"),
        "url": detail_url(e),
    }


def fetch_rentals(session) -> dict:
    found = {}
    for loc in resolve_locality(session):
        for main in (1, 2):
            for page in range(MAX_PAGES):
                params = {"category_main_cb": main, "category_type_cb": 2,
                          "limit": PER_PAGE, "offset": page * PER_PAGE, **loc}
                r = session.get(f"{API}/estates/search", params=params, headers=HEADERS, timeout=30)
                r.raise_for_status()
                js = r.json()
                estates = js.get("results") or []
                for e in estates:
                    if e.get("hash_id") and in_town(e):
                        item = compact(e)
                        found[item["id"]] = item
                total = (js.get("pagination") or {}).get("total") or 0
                if not estates or (page + 1) * PER_PAGE >= total:
                    break
                time.sleep(1.5)
    log.info("Аренда в %s: %d объявлений", config.HOUSING_TOWN, len(found))
    return found
