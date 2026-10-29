# Holýšov бот — работа и аренда

Источники аренды: Sreality, iDNES Reality, Bezrealitky и публичные Telegram-каналы (`TELEGRAM_CHANNELS` в config.py). Telegram-бот присылает вакансии в Holýšov и рядом (данные Úřad práce ČR) и аренду только в Holýšov (Sreality.cz).
Ночные и 3-сменные вакансии скрыты, вакансии «vhodné pro mladistvé» отмечены ⭐.

Работает на GitHub Actions: раз в час запускается `run_once.py`, обновляет данные, присылает новое и отвечает на команды.
Состояние хранится в ветке `state` (файл `bot.db`).

Команды: `/jobs`, `/flats`, `/plzen`, `/only17`, `/status`, `/stop`. Бот отвечает при следующем запуске, до часа.

Настройка: секрет `BOT_TOKEN` в Settings → Secrets and variables → Actions. Города и фильтры — `config.py`.
