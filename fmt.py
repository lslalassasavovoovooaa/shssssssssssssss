# -*- coding: utf-8 -*-
"""Текст сообщений (HTML для Telegram)."""
from html import escape

import config


def _money(v):
    return f"{int(v):,}".replace(",", " ")


def _salary(job):
    a, b = job.get("salary_from"), job.get("salary_to")
    unit = "Kč/hod" if job.get("hourly") else "Kč/měs"
    if a and b and a != b:
        return f"{_money(a)}–{_money(b)} {unit}"
    if a or b:
        return f"{_money(a or b)} {unit}"
    return None


def job_text(job, new=False) -> str:
    lines = [("🆕 " if new else "💼 ") + f"<b>{escape(job['title'])}</b>"]
    if job.get("employer"):
        lines.append(f"🏢 {escape(job['employer'])}")
    lines.append(f"📍 {escape(job['town'])}")
    sal = _salary(job)
    if sal:
        lines.append(f"💰 {sal}")
    shift = job.get("shift")
    if shift or job.get("hours_week"):
        parts = [escape(shift)] if shift else []
        if job.get("hours_week"):
            parts.append(f"{int(job['hours_week'])} h/týden")
        lines.append("🕐 " + " · ".join(parts))
    if job.get("relation"):
        lines.append(f"📄 {escape(job['relation'])}")
    if job.get("education"):
        lines.append(f"🎓 {escape(job['education'])}")
    if job.get("minor_ok"):
        lines.append("⭐ <b>Vhodné pro mladistvé do 18 let</b>")
    if job.get("info"):
        lines.append(f"<i>{escape(job['info'])}</i>")
    contact = []
    if job.get("phone"):
        contact.append(f"📞 {escape(job['phone'])}")
    if job.get("email"):
        contact.append(f"✉️ {escape(job['email'])}")
    if contact:
        lines.append(" ".join(contact))
    links = [f'<a href="{escape(config.UP_DETAIL_URL.format(id=job["id"]), quote=True)}">Úřad práce</a>']
    web = job.get("web")
    if web and web.startswith(("http://", "https://")):
        links.append(f'<a href="{escape(web, quote=True)}">web firmy</a>')
    ref = f" · č. {escape(job['ref'])}" if job.get("ref") else ""
    lines.append("🔗 " + " · ".join(links) + ref)
    return "\n".join(lines)


def flat_text(item, new=False) -> str:
    price = item.get("price")
    price_s = f"{_money(price)} Kč/měsíc" if price and price > 1 else "cena dohodou / info v RK"
    return "\n".join([
        ("🆕 " if new else "🏠 ") + f"<b>{escape(item['title'])}</b>",
        f"📍 {escape(item.get('locality') or '')}",
        f"💰 {price_s}",
        f'🔗 <a href="{escape(item["url"], quote=True)}">Sreality.cz</a>',
    ])


def job_visible(job, user) -> bool:
    if not user.get("plzen") and job.get("town") == config.PLZEN_NAME:
        return False
    if user.get("only17") and not job.get("minor_ok"):
        return False
    return True


def sort_jobs(jobs):
    """Holýšov первым, потом свежие."""
    return sorted(jobs, key=lambda j: (j.get("town") != "Holýšov", -_ts(j.get("inserted"))))


def _ts(s):
    # '2026-10-28T09:15:00...' -> число для сортировки
    try:
        return int("".join(ch for ch in (s or "")[:19] if ch.isdigit()) or 0)
    except ValueError:
        return 0
