# -*- coding: utf-8 -*-
"""Публичные Telegram-каналы и группы: посты про аренду жилья в Holýšov (веб-превью t.me/s/...)."""
import html
import logging
import re

import config
from util import contains_word, norm

log = logging.getLogger(__name__)

POST = re.compile(r'<div class="tgme_widget_message_wrap.*?(?=<div class="tgme_widget_message_wrap|\Z)', re.S)
RENT_WORDS = ("pronaj", "k pronajmu", "nabizim", "pronajmu", "byt ", "dum ", "аренд", "сдам", "квартир")


def _text(fragment):
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def fetch_channel_posts(session, channel) -> dict:
    r = session.get(f"https://t.me/s/{channel}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    found = {}
    for block in POST.findall(r.text):
        post = re.search(r'data-post="([^"]+)"', block)
        body = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        if not (post and body):
            continue
        text = _text(body.group(1))
        if not contains_word(text, config.HOUSING_TOWN):
            continue
        if not any(word in norm(text) for word in RENT_WORDS):
            continue
        found[f"tg:{post.group(1)}"] = {
            "id": f"tg:{post.group(1)}",
            "title": text.split("\n", 1)[0][:90],
            "locality": text[:300],
            "price": None,
            "url": f"https://t.me/{post.group(1)}",
            "site": f"Telegram @{channel}",
        }
    return found


def fetch_channels(session) -> dict:
    found = {}
    for channel in config.TELEGRAM_CHANNELS:
        try:
            found.update(fetch_channel_posts(session, channel))
        except Exception as e:
            log.warning("Канал %s не прочитался: %s", channel, e)
    log.info("Telegram-каналы: %d постов", len(found))
    return found
