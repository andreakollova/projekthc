from __future__ import annotations

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify

app = Flask(__name__)

def get_conn():
    # použije tvoje env premenné (tie isté ako Storage/build_postgres_url)
    return psycopg2.connect(
        os.environ["DATABASE_URL"],  # alebo poskladané z PGHOST...
        cursor_factory=RealDictCursor,
        connect_timeout=10,
        sslmode="require",
    )

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/articles")
def articles():
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT url, type, title, date_text, date_iso, card_image_url, header_image_url, updated_at
                FROM articles
                ORDER BY date_iso DESC NULLS LAST, updated_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            rows = cur.fetchall()
    return jsonify(rows)

@app.get("/matches")
def matches():
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    status = request.args.get("status")  # None / played / upcoming

    q = """
        SELECT match_key, status, date_text, date_iso, round, venue,
               team_home, team_away, logo_home_url, logo_away_url,
               score, is_win, score_periods, updated_at
        FROM matches
    """
    params = []
    if status in ("played", "upcoming"):
        q += " WHERE status = %s"
        params.append(status)

    q += " ORDER BY date_iso DESC NULLS LAST, updated_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(q, tuple(params))
            rows = cur.fetchall()
    return jsonify(rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
