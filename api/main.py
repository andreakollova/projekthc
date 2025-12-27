from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from api.db import db

# Načíta .env z rootu projektu (lokálne). Na Renderi sa env rieši cez dashboard.
load_dotenv()

app = FastAPI(title="HC Košice API", version="1.0.0")

# Ak budeš volať API z web appky (frontend), CORS sa hodí.
# Neskôr to obmedz na konkrétne domény.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init()


@app.on_event("shutdown")
def _shutdown() -> None:
    db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/articles")
def list_articles(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Fulltext v title (ILIKE)"),
    type: str | None = Query(None, description="type1/type2"),
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []

    if q:
        where.append("title ILIKE %s")
        params.append(f"%{q}%")

    if type:
        where.append("type = %s")
        params.append(type)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
            url, type, title, date_text, date_iso,
            card_image_url, header_image_url,
            match_datetime_text, match_datetime_iso, match_round, match_score,
            match_is_win, match_logo_home_url, match_logo_away_url,
            content_text
        FROM articles
        {where_sql}
        ORDER BY COALESCE(date_iso, '') DESC, title ASC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with db.conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items = [
        {
            "url": r[0],
            "type": r[1],
            "title": r[2],
            "date_text": r[3],
            "date_iso": r[4],
            "card_image_url": r[5],
            "header_image_url": r[6],
            "match_datetime_text": r[7],
            "match_datetime_iso": r[8],
            "match_round": r[9],
            "match_score": r[10],
            "match_is_win": r[11],
            "match_logo_home_url": r[12],
            "match_logo_away_url": r[13],
            "content_text": r[14],
        }
        for r in rows
    ]

    return {"items": items, "limit": limit, "offset": offset}


@app.get("/articles/by-url")
def get_article_by_url(url: str) -> dict[str, Any]:
    sql = """
        SELECT
            url, type, title, date_text, date_iso,
            card_image_url, header_image_url,
            match_datetime_text, match_datetime_iso, match_round, match_score,
            match_is_win, match_logo_home_url, match_logo_away_url,
            content_html, content_text
        FROM articles
        WHERE url = %s
        LIMIT 1
    """

    with db.conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (url,))
            row = cur.fetchone()

    if not row:
        return {"found": False, "item": None}

    item = {
        "url": row[0],
        "type": row[1],
        "title": row[2],
        "date_text": row[3],
        "date_iso": row[4],
        "card_image_url": row[5],
        "header_image_url": row[6],
        "match_datetime_text": row[7],
        "match_datetime_iso": row[8],
        "match_round": row[9],
        "match_score": row[10],
        "match_is_win": row[11],
        "match_logo_home_url": row[12],
        "match_logo_away_url": row[13],
        "content_html": row[14],
        "content_text": row[15],
    }

    return {"found": True, "item": item}


@app.get("/matches")
def list_matches(
    status: str | None = Query(None, description="upcoming/played"),
    limit: int = Query(50, ge=1, le=400),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []

    if status:
        where.append("status = %s")
        params.append(status)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        {where_sql}
        ORDER BY COALESCE(date_iso, '') DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with db.conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items = [
        {
            "match_key": r[0],
            "status": r[1],
            "date_text": r[2],
            "date_iso": r[3],
            "round": r[4],
            "venue": r[5],
            "team_home": r[6],
            "team_away": r[7],
            "logo_home_url": r[8],
            "logo_away_url": r[9],
            "score": r[10],
            "is_win": r[11],
            "score_periods": r[12],
        }
        for r in rows
    ]

    return {"items": items, "limit": limit, "offset": offset}
