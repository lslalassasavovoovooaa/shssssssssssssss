# -*- coding: utf-8 -*-
"""Один проход бота для GitHub Actions: обновить данные, разослать новое, ответить на команды."""
import asyncio
import logging
import os
import sys
import time

import bot

log = logging.getLogger("run_once")


async def answer_commands(app):
    offset = int(bot.db.get_meta("tg_offset") or 0)
    updates = await app.bot.get_updates(offset=offset or None, timeout=0,
                                        allowed_updates=["message"])
    for update in updates:
        try:
            await app.process_update(update)
        except Exception:
            log.exception("Ошибка в обработке апдейта %s", update.update_id)
        bot.db.set_meta("tg_offset", update.update_id + 1)
    log.info("Команд обработано: %d", len(updates))


async def run(token):
    app = bot.build_app(token)
    await app.initialize()
    try:
        for kind in ("flats", "jobs"):
            try:
                result = await bot.refresh(kind, app)
                log.info("%s: %s", kind, result)
            except Exception:
                log.exception("Ошибка при проверке %s", kind)
        await answer_commands(app)
        await bot.send_flat_digest(app)
        if bot.db.get_meta("commands_set") is None:
            await bot.on_startup(app)
            bot.db.set_meta("commands_set", int(time.time()))
    finally:
        await app.shutdown()


def main():
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Нет BOT_TOKEN: добавь секрет в Settings -> Secrets and variables -> Actions")
    asyncio.run(run(token))


if __name__ == "__main__":
    main()
