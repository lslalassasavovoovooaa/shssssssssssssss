# -*- coding: utf-8 -*-
"""Telegram-бот: вакансии возле Holýšov и аренда в Holýšov."""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from telegram import BotCommand, LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import fmt
import housing
import jobs
from db import DB

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")

TZ = ZoneInfo(config.TIMEZONE)
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
db = DB(config.DB_PATH)
session = requests.Session()
locks = {"jobs": asyncio.Lock(), "flats": asyncio.Lock()}

HELP = (
    "Привет! Я ищу:\n"
    "💼 <b>работу</b> возле Holýšov (данные Úřad práce ČR)\n"
    "🏠 <b>аренду</b> квартир и домов только в Holýšov (Sreality.cz)\n\n"
    "Новые объявления пришлю сам (проверка раз в час). На команды отвечаю при следующей проверке — до часа. Команды:\n"
    "/jobs — вакансии сейчас\n"
    "/flats — аренда сейчас\n"
    "/plzen — вкл/выкл вакансии в Plzni\n"
    "/only17 — только вакансии с пометкой «для mladistvých»\n"
    "/status — когда была проверка\n"
    "/stop — не присылать уведомления\n\n"
    "Ночные и 3-сменные вакансии я не показываю: до 18 лет ночью работать нельзя."
)


# ---------------- отправка ----------------
async def send(bot, chat_id, text, preview=False):
    for _ in range(3):
        try:
            await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML,
                                   link_preview_options=None if preview else NO_PREVIEW)
            return True
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Forbidden:
            db.set_active(chat_id, False)  # пользователь заблокировал бота
            return False
        except TelegramError as e:
            log.warning("Не отправилось в %s: %s", chat_id, e)
            return False
    return False


async def send_list(bot, chat_id, texts, more_hint, preview=False):
    for t in texts[:config.MAX_NOTIFY_PER_RUN]:
        if not await send(bot, chat_id, t, preview):
            return
        await asyncio.sleep(0.4)
    rest = len(texts) - config.MAX_NOTIFY_PER_RUN
    if rest > 0:
        await send(bot, chat_id, f"…и ещё {rest}. {more_hint}")


# ---------------- обновление данных ----------------
async def refresh(kind, app, notify=True):
    """Скачать свежие объявления, сохранить, разослать новые. Возвращает (всего, новых) или None."""
    async with locks[kind]:
        first_run = db.get_meta(f"{kind}_last_run") is None
        if kind == "jobs":
            items, lm = await asyncio.to_thread(jobs.fetch_jobs, session, db.get_meta("jobs_lm"))
            if items is None:
                return None  # файл на сервере не менялся
        else:
            items = await asyncio.to_thread(housing.fetch_rentals, session)
            lm = None
        new_ids = db.sync(kind, items)
        if lm:
            db.set_meta("jobs_lm", lm)
        log.info("%s: всего %d, новых %d", kind, len(items), len(new_ids))
        if notify and not first_run and new_ids:
            await broadcast(app, kind, [items[i] for i in new_ids])
        return len(items), len(new_ids)


async def broadcast(app, kind, new_items):
    for user in db.active_users():
        if kind == "jobs":
            visible = fmt.sort_jobs([j for j in new_items if fmt.job_visible(j, user)])
            texts = [fmt.job_text(j, new=True) for j in visible]
            hint, preview = "Все вакансии: /jobs", False
        else:
            texts = [fmt.flat_text(f, new=True) for f in new_items]
            hint, preview = "Всё жильё: /flats", True
        if texts:
            await send_list(app.bot, user["chat_id"], texts, hint, preview)


# ---------------- команды ----------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.add_user(update.effective_chat.id)
    await update.message.reply_html(HELP)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.set_active(update.effective_chat.id, False)
    await update.message.reply_text("Уведомления выключены. Включить снова — /start")


async def cmd_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = db.get_user(chat_id)
    items = fmt.sort_jobs([j for j in db.current("jobs") if fmt.job_visible(j, user)])
    if not items:
        msg = ("Вакансий пока нет в базе — данные ещё не загружены, попробуй после следующей проверки."
               if db.get_meta("jobs_last_run") is None else "Сейчас подходящих вакансий нет.")
        await update.message.reply_text(msg)
        return
    await update.message.reply_text(f"Вакансий: {len(items)}. Показываю {min(len(items), config.LIST_LIMIT)} "
                                    f"(сначала Holýšov, потом самые новые).")
    for j in items[:config.LIST_LIMIT]:
        await send(context.bot, chat_id, fmt.job_text(j))
        await asyncio.sleep(0.3)


async def cmd_flats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = db.current("flats")
    if not items:
        msg = ("Данные ещё не загружены, попробуй после следующей проверки."
               if db.get_meta("flats_last_run") is None else
               f"Сейчас на Sreality нет аренды в {config.HOUSING_TOWN}. Как появится — пришлю.")
        await update.message.reply_text(msg)
        return
    await update.message.reply_text(f"Аренда в {config.HOUSING_TOWN}: {len(items)}")
    for f in items[:config.LIST_LIMIT]:
        await send(context.bot, chat_id, fmt.flat_text(f), preview=True)
        await asyncio.sleep(0.3)


async def cmd_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = "plzen" if update.message.text.lstrip("/").startswith("plzen") else "only17"
    on = db.toggle(update.effective_chat.id, field)
    if field == "plzen":
        text = "Вакансии в Plzni: " + ("✅ показываю" if on else "❌ скрыты")
    else:
        text = ("⭐ Показываю только вакансии с пометкой «vhodné pro mladistvé». Их мало — "
                "многие работодатели берут с 17 лет и без пометки." if on
                else "Показываю все дневные вакансии.")
    await update.message.reply_text(text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def when(key):
        v = db.get_meta(key)
        return datetime.fromtimestamp(float(v), TZ).strftime("%d.%m. %H:%M") if v else "ещё не было"
    user = db.get_user(update.effective_chat.id)
    await update.message.reply_text(
        f"Вакансии: последняя загрузка {when('jobs_last_run')}, в базе {len(db.current('jobs'))}\n"
        f"Аренда: последняя проверка {when('flats_last_run')}, в базе {len(db.current('flats'))}\n"
        f"Plzeň: {'вкл' if user['plzen'] else 'выкл'} · только для 17: {'да' if user['only17'] else 'нет'}\n"
        f"Уведомления: {'вкл' if user['active'] else 'выкл'}")


async def on_startup(app: Application):
    await app.bot.set_my_commands([
        BotCommand("jobs", "Вакансии возле Holýšov"),
        BotCommand("flats", "Аренда в Holýšov"),
        BotCommand("plzen", "Вкл/выкл Plzeň"),
        BotCommand("only17", "Только для mladistvých"),
        BotCommand("status", "Статус"),
        BotCommand("stop", "Выключить уведомления"),
    ])


def build_app(token):
    app = Application.builder().token(token).post_init(on_startup).build()
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("flats", cmd_flats))
    app.add_handler(CommandHandler(["plzen", "only17"], cmd_toggle))
    app.add_handler(CommandHandler("status", cmd_status))
    return app
