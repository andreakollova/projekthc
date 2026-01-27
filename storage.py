# storage.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from db import build_postgres_url


@dataclass
class StorageStats:
    articles_inserted: int = 0
    articles_updated: int = 0
    matches_upserted: int = 0


class Storage:
    """
    PostgreSQL storage (CleverCloud).
    Používa jedno spojenie na celý beh scraperu.
    """

    def __init__(self) -> None:
        self.db_url = build_postgres_url()

        self.conn = psycopg2.connect(
            self.db_url,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
            sslmode="require",
        )
        self.conn.autocommit = False

        self.stats = StorageStats()

    def close(self) -> None:
        try:
            if self.conn and not self.conn.closed:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                self.conn.close()
        except Exception:
            pass

    def _commit(self) -> None:
        try:
            self.conn.commit()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise

    def init_schema(self) -> None:
        """
        Vytvorí tabuľky v Postgrese – bezpečne, iba ak neexistujú.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS http_meta (
                url TEXT PRIMARY KEY,
                etag TEXT,
                last_modified TEXT,
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                type TEXT,
                title TEXT,
                date_text TEXT,
                date_iso TEXT,
                card_image_url TEXT,
                header_image_url TEXT,

                match_datetime_text TEXT,
                match_datetime_iso TEXT,
                match_round TEXT,
                match_score TEXT,
                match_is_win INTEGER,
                match_logo_home_url TEXT,
                match_logo_away_url TEXT,

                content_html TEXT,
                content_text TEXT,

                last_seen_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            """)

            # match_key je PRIMARY KEY => unique je už automaticky garantované
            cur.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_key TEXT PRIMARY KEY,
                status TEXT, -- upcoming / played
                date_text TEXT,
                date_iso TEXT,
                round TEXT,
                venue TEXT, -- Doma/Vonku
                team_home TEXT,
                team_away TEXT,
                logo_home_url TEXT,
                logo_away_url TEXT,

                score TEXT,
                is_win INTEGER,
                score_periods TEXT,

                last_seen_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id BIGSERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ DEFAULT now(),
                finished_at TIMESTAMPTZ,
                request_count INTEGER,
                notes TEXT
            );
            """)

        self._commit()

    # --- http_meta ---
    def get_meta(self, url: str) -> Optional[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT url, etag, last_modified FROM http_meta WHERE url = %s", (url,))
            row = cur.fetchone()
            return dict(row) if row else None

    def upsert_meta(self, url: str, etag: str | None, last_modified: str | None) -> None:
        with self.conn.cursor() as cur:
            cur.execute("""
            INSERT INTO http_meta (url, etag, last_modified, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (url) DO UPDATE SET
                etag = EXCLUDED.etag,
                last_modified = EXCLUDED.last_modified,
                updated_at = now();
            """, (url, etag, last_modified))
        self._commit()

    # --- articles ---
    def article_exists(self, url: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM articles WHERE url = %s LIMIT 1", (url,))
            return cur.fetchone() is not None

    def upsert_article(self, data: dict[str, Any]) -> tuple[bool, bool]:
        """
        Returns (inserted, updated)
        """
        with self.conn.cursor() as cur:
            cur.execute("SELECT url FROM articles WHERE url = %s", (data["url"],))
            existing = cur.fetchone()

            if not existing:
                cur.execute("""
                INSERT INTO articles (
                  url, type, title, date_text, date_iso, card_image_url, header_image_url,
                  match_datetime_text, match_datetime_iso, match_round, match_score, match_is_win,
                  match_logo_home_url, match_logo_away_url,
                  content_html, content_text,
                  last_seen_at, updated_at
                ) VALUES (
                  %(url)s, %(type)s, %(title)s, %(date_text)s, %(date_iso)s, %(card_image_url)s, %(header_image_url)s,
                  %(match_datetime_text)s, %(match_datetime_iso)s, %(match_round)s, %(match_score)s, %(match_is_win)s,
                  %(match_logo_home_url)s, %(match_logo_away_url)s,
                  %(content_html)s, %(content_text)s,
                  now(), now()
                );
                """, data)
                self._commit()
                self.stats.articles_inserted += 1
                return True, False

            cur.execute("""
            UPDATE articles SET
              type = %(type)s,
              title = %(title)s,
              date_text = %(date_text)s,
              date_iso = %(date_iso)s,
              card_image_url = %(card_image_url)s,
              header_image_url = %(header_image_url)s,

              match_datetime_text = %(match_datetime_text)s,
              match_datetime_iso = %(match_datetime_iso)s,
              match_round = %(match_round)s,
              match_score = %(match_score)s,
              match_is_win = %(match_is_win)s,
              match_logo_home_url = %(match_logo_home_url)s,
              match_logo_away_url = %(match_logo_away_url)s,

              content_html = %(content_html)s,
              content_text = %(content_text)s,
              last_seen_at = now(),
              updated_at = now()
            WHERE url = %(url)s;
            """, data)

        self._commit()
        self.stats.articles_updated += 1
        return False, True

    # --- matches ---
    def upsert_match(self, data: dict[str, Any]) -> tuple[bool, bool]:
        """
        UPSERT match podľa match_key.
        Returns (inserted, updated)

        Poznámka: match_key musí byť stabilný (bez statusu), inak vznikajú duplicity.
        """
        with self.conn.cursor() as cur:
            # x-max = 0 znamená, že INSERT sa naozaj vložil (nebol konflikt)
            cur.execute("""
            INSERT INTO matches (
              match_key, status, date_text, date_iso, round, venue,
              team_home, team_away, logo_home_url, logo_away_url,
              score, is_win, score_periods,
              last_seen_at, updated_at
            ) VALUES (
              %(match_key)s, %(status)s, %(date_text)s, %(date_iso)s, %(round)s, %(venue)s,
              %(team_home)s, %(team_away)s, %(logo_home_url)s, %(logo_away_url)s,
              %(score)s, %(is_win)s, %(score_periods)s,
              now(), now()
            )
            ON CONFLICT (match_key) DO UPDATE SET
              status = EXCLUDED.status,
              date_text = EXCLUDED.date_text,
              date_iso = EXCLUDED.date_iso,
              round = EXCLUDED.round,
              venue = EXCLUDED.venue,
              team_home = EXCLUDED.team_home,
              team_away = EXCLUDED.team_away,
              logo_home_url = EXCLUDED.logo_home_url,
              logo_away_url = EXCLUDED.logo_away_url,
              score = EXCLUDED.score,
              is_win = EXCLUDED.is_win,
              score_periods = EXCLUDED.score_periods,
              last_seen_at = now(),
              updated_at = now()
            RETURNING (xmax = 0) AS inserted;
            """, data)

            row = cur.fetchone()
            inserted = bool(row["inserted"]) if row and "inserted" in row else False

        self._commit()

        self.stats.matches_upserted += 1
        return inserted, (not inserted)
