# db.py
# Bezpečné DB pripojenie – žiadne heslá napevno v kóde.
# Použi ENV premenné (Render/Windows/Linux) alebo .env (lokálne).
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
from urllib.parse import quote_plus

def build_postgres_url() -> str:
    """
    Vytvorí DATABASE_URL pre PostgreSQL z ENV premenných.
    Podporuje aj priamu DATABASE_URL, ak ju už máš nastavenú.
    """

    # 1) Ak už existuje DATABASE_URL (napr. Render), použijeme ju
    direct = os.getenv("DATABASE_URL")
    if direct:
        return direct

    # 2) Inak poskladáme URL z jednotlivých premenných
    host = os.getenv("PGHOST", "").strip()
    port = os.getenv("PGPORT", "").strip()
    dbname = os.getenv("PGDATABASE", "").strip()
    user = os.getenv("PGUSER", "").strip()
    password = os.getenv("PGPASSWORD", "")

    missing = [k for k, v in {
        "PGHOST": host,
        "PGPORT": port,
        "PGDATABASE": dbname,
        "PGUSER": user,
        "PGPASSWORD": password,
    }.items() if not v]

    if missing:
        raise RuntimeError(
            "Chýbajú ENV premenné pre DB pripojenie: "
            + ", ".join(missing)
            + "\nNastav ich lokálne alebo v Render/CleverCloud."
        )

    # password musí byť URL-encoded
    password_enc = quote_plus(password)

    # SSL – CleverCloud často vyžaduje SSL; ak nie, môžeš dať 'disable'
    sslmode = os.getenv("PGSSLMODE", "require").strip()

    return f"postgresql://{user}:{password_enc}@{host}:{port}/{dbname}?sslmode={sslmode}"


def print_connection_hint() -> None:
    """
    Pomocná funkcia – vypíše, či vidí ENV premenné (bez hesla).
    """
    host = os.getenv("PGHOST", "").strip()
    port = os.getenv("PGPORT", "").strip()
    dbname = os.getenv("PGDATABASE", "").strip()
    user = os.getenv("PGUSER", "").strip()
    sslmode = os.getenv("PGSSLMODE", "require").strip()

    print("DB nastavenia (bez hesla):")
    print(f"  PGHOST: {host}")
    print(f"  PGPORT: {port}")
    print(f"  PGDATABASE: {dbname}")
    print(f"  PGUSER: {user}")
    print(f"  PGSSLMODE: {sslmode}")


if __name__ == "__main__":
    # Rýchly test: python db.py
    print_connection_hint()
    url = build_postgres_url()
    # bezpečne vypíšeme URL bez hesla
    safe_url = url.replace(os.getenv("PGPASSWORD", ""), "***") if os.getenv("PGPASSWORD") else url
    print(f"\nDATABASE_URL (safe): {safe_url}")
