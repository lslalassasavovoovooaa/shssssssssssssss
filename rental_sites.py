# -*- coding: utf-8 -*-
"""Аренда в Holýšov с других сайтов: iDNES Reality и Bezrealitky."""
import html
import logging
import re

import config
from util import contains_word

log = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "cs,en;q=0.8",
}
IDNES_PAGES = ("byty", "domy")
IDNES_ITEM = re.compile(r'<div class="c-products__item">(.*?)</article>', re.S)
BEZ_API = "https://api.bezrealitky.cz/graphql/"
BEZ_HOLYSOV_OSM = "R439251"
BEZ_QUERY = """query($ids:[ID]){listAdverts(offerType:[PRONAJEM],estateType:[BYT,DUM],regionOsmIds:$ids,
limit:60,offset:0,order:TIMEORDER_DESC){list{id uri address(locale:CS) surface disposition estateType price charges}}}"""


def _text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _digits(value):
    cleaned = re.sub(r"[^\d]", "", value or "")
    return int(cleaned) if cleaned else None


def fetch_idnes(session) -> dict:
    found = {}
    slug = config.HOUSING_TOWN.lower().replace("ý", "y").replace("š", "s")
    for kind in IDNES_PAGES:
        r = session.get(f"https://reality.idnes.cz/s/pronajem/{kind}/{slug}/", headers=BROWSER_HEADERS, timeout=30)
        r.raise_for_status()
        for block in IDNES_ITEM.findall(r.text):
            link = re.search(r'href="(https://reality\.idnes\.cz/detail/[^"]+)"', block)
            title = re.search(r'<h2 class="c-products__title">(.*?)</h2>', block, re.S)
            info = re.search(r'<p class="c-products__info">(.*?)</p>', block, re.S)
            price = re.search(r'<p class="c-products__price">(.*?)</p>', block, re.S)
            if not (link and title and info) or not contains_word(_text(info.group(1)), config.HOUSING_TOWN):
                continue
            item_id = link.group(1).rstrip("/").rsplit("/", 1)[-1]
            title_text = _text(title.group(1))
            found[f"idnes:{item_id}"] = {
                "id": f"idnes:{item_id}",
                "title": title_text[:1].upper() + title_text[1:],
                "locality": _text(info.group(1)),
                "price": _digits(_text(price.group(1)).split("Kč")[0]) if price else None,
                "url": link.group(1),
                "site": "iDNES Reality",
            }
    log.info("iDNES Reality: %d объявлений", len(found))
    return found


def _disposition(code):
    match = re.fullmatch(r"DISP_(\d)_(KK|\d)", code or "")
    if not match:
        return "Atypický" if code == "DISP_ATYPICAL" else ""
    return f"{match.group(1)}+{match.group(2).lower()}"


def fetch_bezrealitky(session, osm_id=BEZ_HOLYSOV_OSM) -> dict:
    r = session.post(BEZ_API, json={"query": BEZ_QUERY, "variables": {"ids": [osm_id]}},
                     headers=BROWSER_HEADERS, timeout=30)
    r.raise_for_status()
    adverts = (((r.json().get("data") or {}).get("listAdverts")) or {}).get("list") or []
    found = {}
    for adv in adverts:
        kind = "domu" if adv.get("estateType") == "DUM" else "bytu"
        size = f" {int(adv['surface'])} m²" if adv.get("surface") else ""
        disp = _disposition(adv.get("disposition"))
        item_id = f"bezrealitky:{adv['id']}"
        found[item_id] = {
            "id": item_id,
            "title": f"Pronájem {kind} {disp}{size}".replace("  ", " ").strip(),
            "locality": adv.get("address"),
            "price": adv.get("price"),
            "url": f"https://www.bezrealitky.cz/nemovitosti-byty-domy/{adv['uri']}",
            "site": "Bezrealitky",
        }
    log.info("Bezrealitky: %d объявлений", len(found))
    return found
