# -*- coding: utf-8 -*-
"""Вакансии из открытых данных Úřad práce ČR (data.mpsv.cz).

Файл со всеми вакансиями ЧР большой (сотни МБ), поэтому он читается потоком
(ijson) и в память попадают только вакансии из нужных городов.
"""
import logging

import config
from util import norm, contains_word

log = logging.getLogger(__name__)

BASE = "https://data.mpsv.cz/od/soubory"
VM_URL = f"{BASE}/volna-mista/volna-mista.json"
HEADERS = {"User-Agent": "HolysovJobsBot/1.0 (personal use)"}

_ciselniky_cache = {}


def load_ciselnik(session, name) -> dict:
    """Справочник MPSV: id -> название (cs)."""
    if name in _ciselniky_cache:
        return _ciselniky_cache[name]
    r = session.get(f"{BASE}/ciselniky/{name}.json", headers=HEADERS, timeout=60)
    r.raise_for_status()
    out = {}
    for it in r.json().get("polozky", []):
        nazev = it.get("nazev")
        out[it["id"]] = {
            "name": nazev.get("cs") if isinstance(nazev, dict) else nazev,
            "kod": it.get("kod"),
            "okres": it.get("okres"),
        }
    _ciselniky_cache[name] = out
    return out


def build_town_index(obce: dict, okresy: dict, towns) -> dict:
    """obec_id -> название города, только для городов из config.JOB_TOWNS."""
    wanted = {norm(t): (t, norm(o)) for t, o in towns}
    index = {}
    for obec_id, ob in obce.items():
        key = norm(ob["name"])
        if key not in wanted:
            continue
        town, okres_wanted = wanted[key]
        okres_name = norm((okresy.get(ob.get("okres") or "") or {}).get("name"))
        # если округ не удалось определить — берём по названию
        if okres_name and okres_wanted and okres_name != okres_wanted:
            continue
        index[obec_id] = town
    return index


def _id(obj):
    return obj.get("id") if isinstance(obj, dict) else None


def match_town(vm: dict, town_index: dict, towns):
    """Возвращает название города, если вакансия в одном из нужных городов."""
    mvp = vm.get("mistoVykonuPrace") or {}
    obec_id = _id(mvp.get("obec"))
    if obec_id in town_index:
        return town_index[obec_id]
    for prac in mvp.get("pracoviste") or []:
        adr = prac.get("adresa") or {}
        oid = _id(adr.get("obec"))
        if oid in town_index:
            return town_index[oid]
    text = mvp.get("adresaText")
    if text:
        for t, _ in towns:
            if contains_word(text, t):
                return t
    return None


def _contact(vm):
    pk = vm.get("prvniKontaktSeZamestnavatelem") or {}
    phone = email = None
    for part in (pk.get("komuSeHlasit") or {}, pk.get("kdeSeHlasit") or {}):
        phone = phone or part.get("telefon")
        email = email or part.get("email")
    return phone, email


def compact(vm: dict, town: str, cis: dict) -> dict:
    """Оставляем только то, что нужно для сообщения."""
    smennost_id = _id(vm.get("smennost"))
    vzd_id = _id(vm.get("minPozadovaneVzdelani"))
    typ_mzdy = _id(vm.get("typMzdy")) or ""
    vhodnosti = [_id(v) or "" for v in (vm.get("vhodnostiPracovnihoMista") or [])]
    ppv = [_id(v) or "" for v in (vm.get("pracovnePravniVztahy") or [])]
    phone, email = _contact(vm)
    info = ((vm.get("upresnujiciInformace") or {}).get("cs") or "").strip()
    return {
        "id": str(vm.get("portalId")),
        "ref": vm.get("referencniCislo"),
        "title": ((vm.get("pozadovanaProfese") or {}).get("cs") or "Bez názvu").strip(),
        "employer": (vm.get("zamestnavatel") or {}).get("nazev"),
        "town": town,
        "salary_from": vm.get("mesicniMzdaOd"),
        "salary_to": vm.get("mesicniMzdaDo"),
        "hourly": "hod" in typ_mzdy.lower(),
        "shift_code": (smennost_id or "").split("/")[-1],
        "shift": (cis["smennosti"].get(smennost_id) or {}).get("name"),
        "hours_week": vm.get("pocetHodinTydne"),
        "education": (cis["vzdelani"].get(vzd_id) or {}).get("name"),
        "minor_ok": any(v.endswith("/mladi") for v in vhodnosti),
        "relation": ", ".join(
            (cis["vztahy"].get(p) or {}).get("name") or p.split("/")[-1] for p in ppv if p
        ),
        "phone": phone,
        "email": email,
        "web": vm.get("urlAdresa"),
        "start": vm.get("terminZahajeniPracovnihoPomeru"),
        "inserted": vm.get("datumVlozeni"),
        "info": info[:350] + ("…" if len(info) > 350 else ""),
    }


def _safe_ciselnik(session, name):
    try:
        return load_ciselnik(session, name)
    except Exception as e:  # справочник для красоты — без него тоже работаем
        log.warning("Справочник %s не загрузился: %s", name, e)
        return {}


def iter_vacancies(session):
    import ijson  # импорт здесь, чтобы остальной код работал и без ijson

    with session.get(VM_URL, headers=HEADERS, stream=True, timeout=(20, 600)) as r:
        r.raise_for_status()
        r.raw.decode_content = True  # распаковать gzip на лету
        yield from ijson.items(r.raw, "polozky.item", use_float=True)


def filter_vacancies(vacancies, town_index, towns, cis) -> dict:
    found = {}
    total = 0
    for vm in vacancies:
        total += 1
        town = match_town(vm, town_index, towns)
        if not town:
            continue
        shift_code = (_id(vm.get("smennost")) or "").split("/")[-1]
        if shift_code in config.EXCLUDED_SHIFTS:
            continue
        job = compact(vm, town, cis)
        found[job["id"]] = job
    log.info("Просмотрено вакансий: %d, подходит: %d", total, len(found))
    return found


def fetch_jobs(session, last_modified=None):
    """Возвращает (dict вакансий или None если файл не менялся, Last-Modified)."""
    lm = None
    try:
        h = session.head(VM_URL, headers=HEADERS, timeout=30, allow_redirects=True)
        lm = h.headers.get("Last-Modified") or h.headers.get("ETag")
    except Exception as e:
        log.warning("HEAD не удался (%s), качаю файл целиком", e)
    if lm and last_modified and lm == last_modified:
        log.info("Вакансии не изменились (%s)", lm)
        return None, lm

    obce = load_ciselnik(session, "obce")
    okresy = _safe_ciselnik(session, "okresy")
    town_index = build_town_index(obce, okresy, config.JOB_TOWNS)
    if not town_index:
        log.warning("Не нашёл ни одного города из JOB_TOWNS в справочнике — проверь названия")
    cis = {
        "smennosti": _safe_ciselnik(session, "smennosti"),
        "vzdelani": _safe_ciselnik(session, "vzdelani-detailni-kategorie"),
        "vztahy": _safe_ciselnik(session, "pracovnepravni-vztahy"),
    }
    jobs = filter_vacancies(iter_vacancies(session), town_index, config.JOB_TOWNS, cis)
    return jobs, lm
