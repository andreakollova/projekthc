from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool


class DB:
    def __init__(self) -> None:
        self._pool: SimpleConnectionPool | None = None

    def init(self) -> None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("Chýba DATABASE_URL env premenná.")

        maxconn = int(os.getenv("DB_POOL_MAX", "2"))  # odporúčam aspoň 2
        sslmode = os.getenv("DB_SSLMODE", "require")

        # Pozn.: connect_timeout a keepalives sa nastavujú cez "connect_kwargs"
        # v psycopg2 pooloch neexistuje priamo parameter, ale DSN môže niesť parametre.
        # Preto ich doplníme do DSN, ak tam nie sú.
        dsn = self._ensure_dsn_param(dsn, "sslmode", sslmode)
        dsn = self._ensure_dsn_param(dsn, "connect_timeout", os.getenv("DB_CONNECT_TIMEOUT", "10"))

        # TCP keepalive – pomáha proti idle dropom
        dsn = self._ensure_dsn_param(dsn, "keepalives", "1")
        dsn = self._ensure_dsn_param(dsn, "keepalives_idle", os.getenv("DB_KEEPALIVES_IDLE", "30"))
        dsn = self._ensure_dsn_param(dsn, "keepalives_interval", os.getenv("DB_KEEPALIVES_INTERVAL", "10"))
        dsn = self._ensure_dsn_param(dsn, "keepalives_count", os.getenv("DB_KEEPALIVES_COUNT", "3"))

        self._pool = SimpleConnectionPool(
            minconn=1,
            maxconn=maxconn,
            dsn=dsn,
        )

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

    @contextmanager
    def conn(self) -> Generator:
        """
        Robustný pool context:
        - vezme connection z poolu
        - spraví "ping" (SELECT 1) aby odhalil dead socket ešte pred tvojimi query
        - pri OperationalError/InterfaceError connection zahodí a skúsi ešte raz (1 retry)
        - pri DB chybe rollback + close=True
        """
        if not self._pool:
            raise RuntimeError("DB pool nie je inicializovaný.")

        c = self._pool.getconn()

        # Ak pool vráti zavreté spojenie, zahodíme a vezmeme nové
        if getattr(c, "closed", 0) != 0:
            self._pool.putconn(c, close=True)
            c = self._pool.getconn()

        # 1× retry pre prípad, že DB ukončila idle socket (typicky first request po idle)
        try:
            c = self._ensure_alive(c)
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # zahodiť a skúsiť nové
            try:
                self._pool.putconn(c, close=True)
            except Exception:
                pass
            c = self._pool.getconn()
            c = self._ensure_alive(c)

        try:
            yield c

        except psycopg2.Error:
            # DB chyba -> rollback + vyhodiť z poolu
            try:
                c.rollback()
            except Exception:
                pass
            self._pool.putconn(c, close=True)
            raise

        except Exception:
            # iná chyba -> rollback + vrátiť späť
            try:
                c.rollback()
            except Exception:
                pass
            self._pool.putconn(c)
            raise

        else:
            # OK -> vrátiť späť
            self._pool.putconn(c)

    # -------------------
    # Helpers
    # -------------------
    def _ensure_alive(self, c):
        """
        Overí, že connection je reálne použiteľný (nie iba closed==0).
        Keď je socket dead, SELECT 1 hodí OperationalError / InterfaceError.
        """
        if getattr(c, "closed", 0) != 0:
            raise psycopg2.InterfaceError("Connection is closed")

        # krátky ping
        with c.cursor() as cur:
            cur.execute("SELECT 1;")
            _ = cur.fetchone()

        return c

    def _ensure_dsn_param(self, dsn: str, key: str, value: str) -> str:
        """
        Doplň param do DSN stringu, ak tam ešte nie je.
        Funguje pre DSN typu:
          - postgresql://user:pass@host:port/db?x=1
          - alebo keyword DSN "host=... dbname=..."
        """
        if not value:
            return dsn

        # URI DSN
        if "://" in dsn:
            # už má query?
            if "?" in dsn:
                base, qs = dsn.split("?", 1)
                # ak key už existuje, nemeníme
                if any(part.split("=", 1)[0] == key for part in qs.split("&") if "=" in part):
                    return dsn
                return f"{base}?{qs}&{key}={value}"
            else:
                return f"{dsn}?{key}={value}"

        # keyword DSN (host=... dbname=...)
        if f"{key}=" in dsn:
            return dsn
        return f"{dsn} {key}={value}"


db = DB()
