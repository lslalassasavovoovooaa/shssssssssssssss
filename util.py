# -*- coding: utf-8 -*-
import math
import re
import unicodedata


def norm(s) -> str:
    """'Holýšov' -> 'holysov' (без диакритики, нижний регистр)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().casefold()


def contains_word(text, word) -> bool:
    """Есть ли слово целиком в тексте (Stod не совпадёт со Stodůlky)."""
    t, w = norm(text), norm(word)
    if not t or not w:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t) is not None


def haversine_km(a, b) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))
