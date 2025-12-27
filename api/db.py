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

        # Pool – stabilné a bezpečné pripojenia (zamedzí 'too many connections')
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
        if not self._pool:
            raise RuntimeError("DB pool nie je inicializovaný.")
        c = self._pool.getconn()
        try:
            yield c
        finally:
            self._pool.putconn(c)


db = DB()
