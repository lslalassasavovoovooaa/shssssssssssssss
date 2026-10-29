# -*- coding: utf-8 -*-
"""SQLite: подписчики, их настройки и уже виденные объявления."""
import json
import sqlite3
import threading
import time


class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock, self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                chat_id INTEGER PRIMARY KEY,
                active INTEGER NOT NULL DEFAULT 1,
                plzen INTEGER NOT NULL DEFAULT 1,
                only17 INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS items(
                kind TEXT NOT NULL,
                id TEXT NOT NULL,
                data TEXT NOT NULL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                PRIMARY KEY(kind, id)
            );
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            """)

    # --- meta ---
    def get_meta(self, key):
        with self.lock:
            row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key, value):
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, str(value)))

    # --- users ---
    def add_user(self, chat_id):
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO users(chat_id) VALUES(?) ON CONFLICT(chat_id) DO UPDATE SET active=1",
                              (chat_id,))

    def set_active(self, chat_id, active):
        with self.lock, self.conn:
            self.conn.execute("UPDATE users SET active=? WHERE chat_id=?", (int(active), chat_id))

    def toggle(self, chat_id, field):
        assert field in ("plzen", "only17")
        self.add_user(chat_id)
        with self.lock, self.conn:
            self.conn.execute(f"UPDATE users SET {field} = 1 - {field} WHERE chat_id=?", (chat_id,))
            row = self.conn.execute(f"SELECT {field} FROM users WHERE chat_id=?", (chat_id,)).fetchone()
        return bool(row[0])

    def get_user(self, chat_id):
        with self.lock:
            row = self.conn.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,)).fetchone()
        return dict(row) if row else {"chat_id": chat_id, "active": 0, "plzen": 1, "only17": 0}

    def active_users(self):
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM users WHERE active=1")]

    # --- items ---
    def sync(self, kind, items: dict) -> list:
        """Сохраняет текущий список объявлений, возвращает id новых."""
        now = time.time()
        new_ids = []
        with self.lock, self.conn:
            known = {r["id"] for r in self.conn.execute("SELECT id FROM items WHERE kind=?", (kind,))}
            for item_id, data in items.items():
                payload = json.dumps(data, ensure_ascii=False)
                if item_id in known:
                    self.conn.execute("UPDATE items SET data=?, last_seen=? WHERE kind=? AND id=?",
                                      (payload, now, kind, item_id))
                else:
                    new_ids.append(item_id)
                    self.conn.execute("INSERT INTO items(kind, id, data, first_seen, last_seen) VALUES(?,?,?,?,?)",
                                      (kind, item_id, payload, now, now))
            self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (f"{kind}_last_run", str(now)))
            # старьё (не видели больше 30 дней) чистим
            self.conn.execute("DELETE FROM items WHERE kind=? AND last_seen < ?", (kind, now - 30 * 86400))
        return new_ids

    def current(self, kind) -> list:
        """Объявления, которые были на сайте при последней проверке (новые первыми)."""
        last_run = self.get_meta(f"{kind}_last_run")
        if not last_run:
            return []
        with self.lock:
            rows = self.conn.execute(
                "SELECT data FROM items WHERE kind=? AND last_seen >= ? ORDER BY first_seen DESC, id DESC",
                (kind, float(last_run) - 1)).fetchall()
        return [json.loads(r["data"]) for r in rows]
