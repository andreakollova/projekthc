from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.pool import SimpleConnectionPool


class DB:
    def __init__(self) -> None:
        self._pool: SimpleConnectionPool | None = None

    def init(self) -> None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("Chýba DATABASE_URL env premenná.")

        self._pool = SimpleConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("DB_POOL_MAX", "5")),
            dsn=dsn,
            sslmode=os.getenv("DB_SSLMODE", "require"),
        )

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

    @contextmanager
    def conn(self) -> Generator:
        """
        Vráti DB connection z poolu.
        - Ak pool vráti už zatvorené / pokazené spojenie, zahodí ho.
        - Ak nastane psycopg2 chyba (EOF, reset, atď.), spojenie sa vyhodí z poolu (close=True).
        - Pri chybách robí rollback.
        """
        if not self._pool:
            raise RuntimeError("DB pool nie je inicializovaný.")

        c = self._pool.getconn()

        # Ak pool náhodou vráti už zavreté spojenie, rovno ho zahoď a vezmi nové
        if getattr(c, "closed", 0) != 0:
            self._pool.putconn(c, close=True)
            c = self._pool.getconn()

        try:
            yield c

        except psycopg2.Error:
            # DB chyba = spojenie môže byť v zlom stave -> rollback + vyhodiť z poolu
            try:
                c.rollback()
            except Exception:
                pass
            self._pool.putconn(c, close=True)
            raise

        except Exception:
            # iná chyba (napr. bug v kóde) -> rollback a vrátiť spojenie späť
            try:
                c.rollback()
            except Exception:
                pass
            self._pool.putconn(c)
            raise

        else:
            # OK -> vrátiť spojenie späť do poolu
            self._pool.putconn(c)


db = DB()
