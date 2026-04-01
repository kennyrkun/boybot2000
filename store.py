import os
import sqlite3
from typing import Optional, Dict, Any, List

class Store:
    """Tiny SQLite-backed store for weather preferences and schedules."""

    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cur = self.db.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_zips (
                channel_id INTEGER PRIMARY KEY,
                zip TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                zip TEXT NOT NULL,
                cadence TEXT NOT NULL,
                hh INTEGER NOT NULL,
                mi INTEGER NOT NULL,
                weekly_days INTEGER,
                tz_name TEXT,
                units TEXT,
                next_run_utc TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_weather_subs_next ON weather_subs(next_run_utc)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_weather_subs_user ON weather_subs(channel_id)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS event_subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                cadence TEXT NOT NULL,
                hh INTEGER NOT NULL,
                mi INTEGER NOT NULL,
                weekly_days INTEGER,
                next_run TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS moon_subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                cadence TEXT NOT NULL,
                hh INTEGER NOT NULL,
                mi INTEGER NOT NULL,
                weekly_days INTEGER,
                next_run TEXT NOT NULL
            )
            """
        )

        cur.execute("DROP TABLE yappers");

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS yappers (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                message_count INTEGER NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                channel_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (channel_id, key)
            )
            """
        )

        self.db.commit()

    def get_user_zip(self, channel_id: int) -> Optional[str]:
        row = self.db.execute("SELECT zip FROM weather_zips WHERE channel_id = ?", (int(channel_id),)).fetchone()
        return row["zip"] if row else None

    def set_user_zip(self, channel_id: int, zip_code: str) -> None:
        self.db.execute(
            """
            INSERT INTO weather_zips(channel_id, zip) VALUES (?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET zip = excluded.zip
            """,
            (int(channel_id), str(zip_code)),
        )
        self.db.commit()

    def add_weather_sub(self, sub: Dict[str, Any]) -> int:
        cur = self.db.cursor()
        cur.execute(
            """
            INSERT INTO weather_subs(channel_id, zip, cadence, hh, mi, weekly_days, tz_name, units, next_run_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(sub["channel_id"]),
                str(sub["zip"]),
                str(sub["cadence"]),
                int(sub["hh"]),
                int(sub["mi"]),
                int(sub.get("weekly_days") or 0),
                str(sub.get("tz_name") or ""),
                str(sub.get("units") or ""),
                str(sub["next_run_utc"]),
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def list_weather_subs(self, channel_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List subscriptions. If channel_id is None, returns all subs."""
        if channel_id is None:
            rows = self.db.execute(
                """
                SELECT id, channel_id, zip, cadence, hh, mi, weekly_days, tz_name, units, next_run_utc
                FROM weather_subs
                ORDER BY next_run_utc ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

        rows = self.db.execute(
            """
            SELECT id, channel_id, zip, cadence, hh, mi, weekly_days, tz_name, units, next_run_utc
            FROM weather_subs
            WHERE channel_id = ?
            ORDER BY next_run_utc ASC
            """,
            (int(channel_id),),
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_weather_sub(self, sub_id: int, requester_id: int) -> bool:
        """Remove a subscription by ID, only if it belongs to requester_id."""
        cur = self.db.cursor()
        cur.execute(
            "DELETE FROM weather_subs WHERE id = ? AND channel_id = ?",
            (int(sub_id), int(requester_id)),
        )
        self.db.commit()
        return cur.rowcount > 0

    def update_weather_sub(self, sub_id: int, next_run_utc: str, **_ignored) -> None:
        self.db.execute("UPDATE weather_subs SET next_run_utc = ? WHERE id = ?", (str(next_run_utc), int(sub_id)))
        self.db.commit()

    def add_event_sub(self, sub: Dict[str, Any]) -> int:
        cur = self.db.cursor()
        cur.execute(
            """
            INSERT INTO event_subs(channel_id, guild_id, cadence, hh, mi, weekly_days, next_run)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(sub["channel_id"]),
                int(sub["guild_id"]),
                str(sub["cadence"]),
                int(sub["hh"]),
                int(sub["mi"]),
                int(sub.get("weekly_days") or 0),
                str(sub["next_run"]),
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def list_event_subs(self, channel_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List event subscriptions. If channel_id is None, returns all subs."""
        if channel_id is None:
            rows = self.db.execute(
                """
                SELECT id, channel_id, guild_id, cadence, hh, mi, weekly_days, next_run
                FROM event_subs
                ORDER BY next_run ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

        rows = self.db.execute(
            """
            SELECT id, channel_id, guild_id, cadence, hh, mi, weekly_days, next_run
            FROM event_subs
            WHERE channel_id = ?
            ORDER BY next_run ASC
            """,
            (int(channel_id),),
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_event_sub(self, sub_id: int, requester_id: int) -> bool:
        """Remove a subscription by channel ID, only if it belongs to requester_id."""
        cur = self.db.cursor()
        cur.execute(
            "DELETE FROM event_subs WHERE id = ? AND channel_id = ?",
            (int(sub_id), int(requester_id)),
        )
        self.db.commit()
        return cur.rowcount > 0

    def update_event_sub(self, sub_id: int, next_run: str, **_ignored) -> None:
        self.db.execute("UPDATE event_subs SET next_run = ? WHERE id = ?", (str(next_run), int(sub_id)))
        self.db.commit()

    def add_moon_sub(self, sub: Dict[str, Any]) -> int:
        cur = self.db.cursor()
        cur.execute(
            """
            INSERT INTO moon_subs(channel_id, cadence, hh, mi, weekly_days, next_run)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(sub["channel_id"]),
                str(sub["cadence"]),
                int(sub["hh"]),
                int(sub["mi"]),
                int(sub.get("weekly_days") or 0),
                str(sub["next_run"]),
            ),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def list_moon_subs(self, channel_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List moon subscriptions. If channel_id is None, returns all subs."""
        if channel_id is None:
            rows = self.db.execute(
                """
                SELECT id, channel_id, cadence, hh, mi, weekly_days, next_run
                FROM moon_subs
                ORDER BY next_run ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

        rows = self.db.execute(
            """
            SELECT id, channel_id, cadence, hh, mi, weekly_days, next_run
            FROM moon_subs
            WHERE channel_id = ?
            ORDER BY next_run ASC
            """,
            (int(channel_id),),
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_moon_sub(self, sub_id: int, requester_id: int) -> bool:
        """Remove a subscription by channel ID, only if it belongs to requester_id."""
        cur = self.db.cursor()
        cur.execute(
            "DELETE FROM moon_subs WHERE id = ? AND channel_id = ?",
            (int(sub_id), int(requester_id)),
        )
        self.db.commit()
        return cur.rowcount > 0

    def update_moon_sub(self, sub_id: int, next_run: str, **_ignored) -> None:
        self.db.execute("UPDATE moon_subs SET next_run = ? WHERE id = ?", (str(next_run), int(sub_id)))
        self.db.commit()

    def increment_yaps(self, user_id: int, guild_id: int):
        self.db.execute("""
        INSERT OR REPLACE INTO yappers 
            (user_id, guild_id, message_count) 
            VALUES
            (
                ?,
                ?,
                IFNULL((SELECT message_count FROM yappers WHERE user_id = ? AND guild_id = ?), 0) + 1
            )
        ;""", (user_id, guild_id, user_id, guild_id))
        self.db.commit()

        rows = self.db.execute("SELECT * FROM yappers WHERE guild_id = ? ORDER BY message_count DESC LIMIT 5", (guild_id)).fetchall()
        return [dict(r) for r in rows]

    def get_top_yappers(self, guild_id: int):
        rows = self.db.execute("SELECT * FROM yappers WHERE guild_id = ? ORDER BY message_count DESC LIMIT 5", (guild_id)).fetchall()
        return [dict(r) for r in rows]

    def get_note(self, channel_id: int, key: str) -> Optional[str]:
        row = self.db.execute(
            "SELECT value FROM notes WHERE channel_id = ? AND key = ?",
            (int(channel_id), str(key)),
        ).fetchone()
        return row["value"] if row else None

    def set_note(self, channel_id: int, key: str, value: str) -> None:
        self.db.execute(
            """
            INSERT INTO notes(channel_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(channel_id, key) DO UPDATE SET value = excluded.value
            """,
            (int(channel_id), str(key), str(value)),
        )
        self.db.commit()

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass