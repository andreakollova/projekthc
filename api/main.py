from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from api.db import db

# Lokálne načíta .env (Render používa Environment Variables v dashboarde)
load_dotenv()

app = FastAPI(title="HC Košice API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # neskôr obmedz na konkrétne domény
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


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "HC Košice API", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# -------------------------
# Articles
# -------------------------
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


@app.get("/articles/latest")
def get_latest_article() -> dict[str, Any]:
    """
    1 najnovší článok – ideálne pre hero background (header_image_url / card_image_url).
    """
    sql = """
        SELECT
            url, type, title, date_text, date_iso,
            card_image_url, header_image_url,
            match_datetime_text, match_datetime_iso, match_round, match_score,
            match_is_win, match_logo_home_url, match_logo_away_url,
            content_text
        FROM articles
        ORDER BY COALESCE(date_iso, '') DESC, updated_at DESC
        LIMIT 1
    """

    with db.conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            r = cur.fetchone()

    if not r:
        return {"found": False, "item": None}

    item = {
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
    return {"found": True, "item": item}


# -------------------------
# Matches
# -------------------------
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


@app.get("/matches/next")
def get_next_match() -> dict[str, Any]:
    """
    Najbližší upcoming zápas (1 kus) – pre hero.
    """
    sql = """
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        WHERE status = 'upcoming'
        ORDER BY COALESCE(date_iso, '') ASC
        LIMIT 1
    """

    with db.conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            r = cur.fetchone()

    if not r:
        return {"found": False, "item": None}

    item = {
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
    return {"found": True, "item": item}


@app.get("/matches/last")
def get_last_played_match() -> dict[str, Any]:
    """
    Posledný odohraný zápas (1 kus) – pre sekundárny blok na homepage.
    """
    sql = """
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        WHERE status = 'played'
        ORDER BY COALESCE(date_iso, '') DESC
        LIMIT 1
    """

    with db.conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            r = cur.fetchone()

    if not r:
        return {"found": False, "item": None}

    item = {
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
    return {"found": True, "item": item}


@app.get("/home")
def home_payload(
    articles_limit: int = Query(6, ge=1, le=30),
    upcoming_limit: int = Query(6, ge=1, le=50),
    played_limit: int = Query(6, ge=1, le=50),
) -> dict[str, Any]:
    """
    Homepage payload – všetko v jednom requeste.
    """
    # latest_article
    sql_latest_article = """
        SELECT
            url, type, title, date_text, date_iso,
            card_image_url, header_image_url,
            match_datetime_text, match_datetime_iso, match_round, match_score,
            match_is_win, match_logo_home_url, match_logo_away_url,
            content_text
        FROM articles
        ORDER BY COALESCE(date_iso, '') DESC, updated_at DESC
        LIMIT 1
    """

    # latest_articles list
    sql_latest_articles = """
        SELECT
            url, type, title, date_text, date_iso,
            card_image_url, header_image_url,
            match_datetime_text, match_datetime_iso, match_round, match_score,
            match_is_win, match_logo_home_url, match_logo_away_url,
            content_text
        FROM articles
        ORDER BY COALESCE(date_iso, '') DESC, updated_at DESC
        LIMIT %s
    """

    # next_match
    sql_next = """
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        WHERE status = 'upcoming'
        ORDER BY COALESCE(date_iso, '') ASC
        LIMIT 1
    """

    # last_match
    sql_last = """
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        WHERE status = 'played'
        ORDER BY COALESCE(date_iso, '') DESC
        LIMIT 1
    """

    # upcoming list
    sql_upcoming = """
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        WHERE status = 'upcoming'
        ORDER BY COALESCE(date_iso, '') ASC
        LIMIT %s
    """

    # played list
    sql_played = """
        SELECT
            match_key, status, date_text, date_iso, round, venue,
            team_home, team_away, logo_home_url, logo_away_url,
            score, is_win, score_periods
        FROM matches
        WHERE status = 'played'
        ORDER BY COALESCE(date_iso, '') DESC
        LIMIT %s
    """

    with db.conn() as conn:
        with conn.cursor() as cur:
            # latest_article
            cur.execute(sql_latest_article)
            la = cur.fetchone()

            # latest_articles
            cur.execute(sql_latest_articles, (articles_limit,))
            lrows = cur.fetchall()

            # next + last
            cur.execute(sql_next)
            nm = cur.fetchone()

            cur.execute(sql_last)
            lm = cur.fetchone()

            # lists
            cur.execute(sql_upcoming, (upcoming_limit,))
            urows = cur.fetchall()

            cur.execute(sql_played, (played_limit,))
            prows = cur.fetchall()

    def map_article(r) -> dict[str, Any]:
        return {
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

    def map_match(r) -> dict[str, Any]:
        return {
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

    latest_article = map_article(la) if la else None
    latest_articles = [map_article(r) for r in lrows] if lrows else []

    next_match = map_match(nm) if nm else None
    last_match = map_match(lm) if lm else None

    upcoming_matches = [map_match(r) for r in urows] if urows else []
    played_matches = [map_match(r) for r in prows] if prows else []

    return {
        "next_match": next_match,
        "last_match": last_match,
        "latest_article": latest_article,
        "latest_articles": latest_articles,
        "upcoming_matches": upcoming_matches,
        "played_matches": played_matches,
    }
