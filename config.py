# -*- coding: utf-8 -*-
"""Настройки бота. Меняй здесь — код трогать не нужно."""

# ---------- РАБОТА ----------
# Города, вакансии в которых бот присылает: (название города, название округа).
# Округ нужен, чтобы не путать одинаковые названия (например, Chotěšov есть два).
JOB_TOWNS = [
    ("Holýšov", "Domažlice"),
    ("Staňkov", "Domažlice"),
    ("Horšovský Týn", "Domažlice"),
    ("Domažlice", "Domažlice"),
    ("Stod", "Plzeň-jih"),
    ("Chotěšov", "Plzeň-jih"),
    ("Dobřany", "Plzeň-jih"),
    ("Přeštice", "Plzeň-jih"),
    ("Nýřany", "Plzeň-sever"),
    ("Plzeň", "Plzeň-město"),   # Plzeň можно выключить в боте командой /plzen
]
PLZEN_NAME = "Plzeň"

# Смены, которые бот НЕ показывает (несовершеннолетним нельзя ночную работу):
# triSm = 3 смены, ctyrSm = 4 смены, nepretrzity = нон-стоп, nocni = ночь, turnus = турнусы
EXCLUDED_SHIFTS = {"triSm", "ctyrSm", "nepretrzity", "nocni", "turnus"}

# Вакансии Úřad práce обновляются 1 раз в день. Бот проверяет, изменился ли файл,
# каждые N часов (проверка дешёвая, большой файл качается только если он новый).
JOBS_CHECK_EVERY_HOURS = 3

# Ссылка на вакансию на сайте Úřad práce ({id} = portalId)
UP_DETAIL_URL = "https://www.uradprace.cz/web/cz/vyhledani-volneho-mista#/volna-mista-detail/{id}"

# ---------- ЖИЛЬЁ ----------
HOUSING_TOWN = "Holýšov"
# Центр Holýšov — запасной фильтр по GPS, если в адресе нет слова Holýšov
HOUSING_CENTER = (49.5936, 13.1013)
HOUSING_RADIUS_KM = 2.0
# Как часто проверять аренду (минуты). Не ставь меньше 30 — не нагружай сайт.
HOUSING_CHECK_EVERY_MIN = 60
# Запасной вариант, если не получилось узнать округ через поиск Sreality:
# номер края в Sreality (Plzeňský kraj). Результаты всё равно фильтруются по Holýšov.
SREALITY_REGION_FALLBACK = [2]

# ---------- ОБЩЕЕ ----------
# Максимум уведомлений за одну проверку (остальное — одной строкой "и ещё N")
MAX_NOTIFY_PER_RUN = 15
# Сколько объявлений показывать по командам /jobs и /flats
LIST_LIMIT = 15
FLATS_LIMIT = 40
TELEGRAM_CHANNELS = []
import os

DB_PATH = os.getenv("BOT_DB", "bot.db")
TIMEZONE = "Europe/Prague"
