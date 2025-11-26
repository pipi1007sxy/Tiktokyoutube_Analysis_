#!/usr/bin/env python3
"""Clean the raw CSV file and reseed the SQLite database in one go."""

from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "Tiktok_youtube.db"
CSV_PATH = PROJECT_ROOT / "youtube_shorts_tiktok_trends_2025.csv"

COUNTRY_NAME_MAP: Dict[str, str] = {
    "AE": "United Arab Emirates",
    "AR": "Argentina",
    "AU": "Australia",
    "BR": "Brazil",
    "CA": "Canada",
    "CN": "China",
    "CO": "Colombia",
    "DE": "Germany",
    "EG": "Egypt",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "ID": "Indonesia",
    "IN": "India",
    "IT": "Italy",
    "JP": "Japan",
    "KE": "Kenya",
    "KR": "South Korea",
    "MA": "Morocco",
    "MX": "Mexico",
    "NG": "Nigeria",
    "NL": "Netherlands",
    "PH": "Philippines",
    "PL": "Poland",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "TR": "Turkey",
    "US": "United States",
    "ZA": "South Africa",
}

PLATFORM_NORMALIZER = {
    "tiktok": "TikTok",
    "tik tok": "TikTok",
    "you tube": "YouTube",
    "youtube": "YouTube",
    "youtube shorts": "YouTube",
}

CREATOR_TIER_MAP = {
    "mega": "Mega",
    "macro": "Macro",
    "mid": "Mid",
    "micro": "Micro",
    "nano": "Nano",
}


def normalize_spaces(value: str) -> str:
    """Collapse internal whitespace for cleaner comparisons."""
    return re.sub(r"\s+", " ", value.strip())


def clean_hashtag(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    text = value.lstrip("#")
    return f"#{text}" if text else ""


def coerce_int(series: pd.Series, *, lower: int | None = None, upper: int | None = None) -> pd.Series:
    coerced = pd.to_numeric(series, errors="coerce").fillna(0).round().astype(int)
    if lower is not None or upper is not None:
        coerced = coerced.clip(lower=lower, upper=upper)
    return coerced


def coerce_float(series: pd.Series, *, lower: float | None = None, upper: float | None = None) -> pd.Series:
    coerced = pd.to_numeric(series, errors="coerce").fillna(0.0)
    if lower is not None or upper is not None:
        coerced = coerced.clip(lower=lower, upper=upper)
    return coerced


def coerce_bool(series: pd.Series) -> pd.Series:
    truthy = {"1", "true", "yes", "y", "t", "on", "weekend"}
    return series.astype(str).str.strip().str.lower().isin(truthy).astype(int)


def split_tags(value: str) -> List[str]:
    if not isinstance(value, str):
        return []
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def normalize_platform(value: str) -> str:
    key = value.strip().lower()
    return PLATFORM_NORMALIZER.get(key, normalize_spaces(value))


def normalize_creator_tier(value: str) -> str:
    key = value.strip().lower()
    return CREATOR_TIER_MAP.get(key, "Mid")


def load_and_clean_dataframe(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df["row_id"] = df["row_id"].astype(str).str.strip()
    df = df[df["row_id"] != ""]
    df = df.drop_duplicates(subset=["row_id"]).reset_index(drop=True)

    # Basic text normalisation
    df["platform"] = df["platform"].astype(str).apply(normalize_platform)
    df = df[df["platform"] != ""]
    df["category"] = (
        df["category"]
        .astype(str)
        .apply(normalize_spaces)
        .replace("", "Misc")
        .str.title()
    )
    df["hashtag"] = df["hashtag"].astype(str).apply(clean_hashtag)
    df["title"] = df["title"].astype(str).apply(normalize_spaces).replace("", "Untitled")
    df["title_keywords"] = df["title_keywords"].astype(str).apply(normalize_spaces)
    df["title_length"] = df["title"].str.len()
    df["author_handle"] = df["author_handle"].astype(str).apply(normalize_spaces)
    df = df[df["author_handle"] != ""]
    df["creator_tier"] = df["creator_tier"].astype(str).apply(normalize_creator_tier)
    df["country_code"] = df["country"].astype(str).str.strip().str.upper()
    df = df[df["country_code"] != ""]
    df["country_name"] = df["country_code"].map(COUNTRY_NAME_MAP).fillna(df["country_code"])
    df["region"] = df["region"].astype(str).apply(normalize_spaces).str.title().replace("", "Unknown")
    df["language"] = df["language"].astype(str).str.strip().str.lower().replace("", "en")

    df["publish_dayofweek"] = df["publish_dayofweek"].astype(str).str.strip().str.title()
    df["publish_period"] = df["publish_period"].astype(str).str.strip().str.title()
    df["event_season"] = df["event_season"].astype(str).str.strip().str.title()
    df["season"] = df["season"].astype(str).str.strip().str.title()

    df["trend_label"] = (
        df["trend_label"].astype(str).str.strip().str.title().replace("", "General")
    )
    df["trend_type"] = (
        df["trend_type"].astype(str).str.strip().str.title().replace("", "General")
    )
    df["source_hint"] = df["source_hint"].astype(str).apply(normalize_spaces).replace("", "N/A")

    # Numeric coercion
    int_columns = [
        "duration_sec",
        "views",
        "likes",
        "comments",
        "shares",
        "saves",
        "dislikes",
        "engagement_total",
        "week_of_year",
        "trend_duration_days",
        "upload_hour",
    ]
    for col in int_columns:
        lower = 0
        upper = None
        if col == "week_of_year":
            lower, upper = 1, 53
        if col == "upload_hour":
            lower, upper = 0, 23
        df[col] = coerce_int(df[col], lower=lower, upper=upper)

    float_columns = [
        "engagement_rate",
        "like_rate",
        "dislike_rate",
        "engagement_per_1k",
        "engagement_like_rate",
        "engagement_comment_rate",
        "engagement_share_rate",
        "avg_watch_time_sec",
        "completion_rate",
        "creator_avg_views",
        "engagement_velocity",
    ]
    for col in float_columns:
        lower = 0.0
        upper = 1.0 if "rate" in col or col == "completion_rate" else None
        df[col] = coerce_float(df[col], lower=lower, upper=upper)

    df["has_emoji"] = coerce_bool(df["has_emoji"])
    df["is_weekend"] = coerce_bool(df["is_weekend"])

    df["publish_date_approx"] = pd.to_datetime(df["publish_date_approx"], errors="coerce")
    df = df.dropna(subset=["publish_date_approx"])
    df["publish_date_approx"] = df["publish_date_approx"].dt.strftime("%Y-%m-%d")
    df["year_month"] = df["publish_date_approx"].str.slice(0, 7)

    df["tags_list"] = df["tags"].astype(str).apply(split_tags)
    df["sample_comment_clean"] = df["sample_comments"].astype(str).str.strip()

    # Ensure device fields are clean
    df["device_type"] = df["device_type"].astype(str).apply(normalize_spaces).replace("", "Unknown")
    df["device_brand"] = df["device_brand"].astype(str).apply(normalize_spaces).replace("", "Unknown")
    df["traffic_source"] = df["traffic_source"].astype(str).apply(normalize_spaces).replace("", "Unknown")

    needed_columns = [
        "row_id",
        "platform",
        "category",
        "hashtag",
        "title",
        "title_keywords",
        "title_length",
        "has_emoji",
        "duration_sec",
        "views",
        "likes",
        "comments",
        "shares",
        "saves",
        "dislikes",
        "engagement_rate",
        "engagement_total",
        "like_rate",
        "dislike_rate",
        "engagement_per_1k",
        "engagement_like_rate",
        "engagement_comment_rate",
        "engagement_share_rate",
        "avg_watch_time_sec",
        "completion_rate",
        "publish_date_approx",
        "year_month",
        "publish_dayofweek",
        "publish_period",
        "event_season",
        "season",
        "week_of_year",
        "country_code",
        "country_name",
        "region",
        "language",
        "author_handle",
        "creator_avg_views",
        "creator_tier",
        "device_type",
        "device_brand",
        "upload_hour",
        "traffic_source",
        "is_weekend",
        "trend_label",
        "trend_type",
        "trend_duration_days",
        "engagement_velocity",
        "source_hint",
        "tags_list",
        "sample_comment_clean",
    ]
    return df[needed_columns].copy()


def backup_database(db_path: Path) -> Path:
    backup_path = db_path.with_suffix(db_path.suffix + ".bak")
    shutil.copy2(db_path, backup_path)
    return backup_path


def clear_existing_tables(conn: sqlite3.Connection) -> None:
    tables = [
        "Content_Tags",
        "Content_Comments",
        "Content",
        "Trend",
        "Device",
        "Author",
        "Country",
    ]
    cur = conn.cursor()
    for table in tables:
        cur.execute(f"DELETE FROM {table}")
    seq_tables = ["Country", "Author", "Device", "Trend", "Content_Tags", "Content_Comments"]
    placeholders = ",".join("?" for _ in seq_tables)
    cur.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", seq_tables)


def seed_countries(conn: sqlite3.Connection, df: pd.DataFrame) -> Dict[str, int]:
    rows = []
    seen = set()
    for _, record in df[["country_code", "country_name", "region", "language"]].iterrows():
        if record["country_code"] in seen:
            continue
        seen.add(record["country_code"])
        rows.append(
            (
                record["country_code"],
                record["country_name"],
                record["region"],
                record["language"],
            )
        )
    conn.executemany(
        "INSERT INTO Country (country_code, country_name, region, language) VALUES (?, ?, ?, ?)",
        rows,
    )
    cur = conn.cursor()
    cur.execute("SELECT country_id, country_code FROM Country")
    return {code: country_id for country_id, code in cur.fetchall()}


def seed_authors(conn: sqlite3.Connection, df: pd.DataFrame) -> Dict[str, int]:
    rows = []
    seen = set()
    for _, record in df[["author_handle", "creator_avg_views", "creator_tier"]].iterrows():
        key = record["author_handle"]
        if key in seen or not key:
            continue
        seen.add(key)
        rows.append((key, float(record["creator_avg_views"]), record["creator_tier"]))
    conn.executemany(
        "INSERT INTO Author (author_handle, creator_avg_views, creator_tier) VALUES (?, ?, ?)",
        rows,
    )
    cur = conn.cursor()
    cur.execute("SELECT author_id, author_handle FROM Author")
    return {handle: author_id for author_id, handle in cur.fetchall()}


def seed_devices(conn: sqlite3.Connection, df: pd.DataFrame) -> Dict[Tuple[str, str, int, str, int], int]:
    rows = []
    seen = set()
    for _, record in df[["device_type", "device_brand", "upload_hour", "traffic_source", "is_weekend"]].iterrows():
        key = (record["device_type"], record["device_brand"], int(record["upload_hour"]), record["traffic_source"], int(record["is_weekend"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
    conn.executemany(
        "INSERT INTO Device (device_type, device_brand, upload_hour, traffic_source, is_weekend) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    cur = conn.cursor()
    cur.execute(
        "SELECT device_id, device_type, device_brand, upload_hour, traffic_source, is_weekend FROM Device"
    )
    return {(row[1], row[2], row[3], row[4], row[5]): row[0] for row in cur.fetchall()}


def seed_trends(conn: sqlite3.Connection, df: pd.DataFrame) -> Dict[Tuple[str, str, int], int]:
    rows = []
    seen = set()
    for _, record in df[["trend_label", "trend_type", "trend_duration_days", "engagement_velocity", "source_hint"]].iterrows():
        key = (record["trend_label"], record["trend_type"], int(record["trend_duration_days"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(key + (float(record["engagement_velocity"]), record["source_hint"]))
    conn.executemany(
        "INSERT INTO Trend (trend_label, trend_type, trend_duration_days, engagement_velocity, source_hint) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    cur = conn.cursor()
    cur.execute("SELECT trend_id, trend_label, trend_type, trend_duration_days FROM Trend")
    return {(row[1], row[2], row[3]): row[0] for row in cur.fetchall()}


def insert_content_and_related(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    country_map: Dict[str, int],
    author_map: Dict[str, int],
    device_map: Dict[Tuple[str, str, int, str, int], int],
    trend_map: Dict[Tuple[str, str, int], int],
) -> Tuple[int, int, int]:
    content_rows: List[Sequence[object]] = []
    tag_rows: List[Tuple[str, str]] = []
    comment_rows: List[Tuple[str, str]] = []

    for record in df.itertuples(index=False):
        country_id = country_map[record.country_code]
        author_id = author_map[record.author_handle]
        device_key = (record.device_type, record.device_brand, int(record.upload_hour), record.traffic_source, int(record.is_weekend))
        device_id = device_map[device_key]
        trend_key = (record.trend_label, record.trend_type, int(record.trend_duration_days))
        trend_id = trend_map[trend_key]

        content_rows.append(
            (
                record.row_id,
                record.platform,
                record.category,
                record.hashtag,
                record.title,
                record.title_keywords,
                int(record.title_length),
                int(record.has_emoji),
                int(record.duration_sec),
                int(record.views),
                int(record.likes),
                int(record.comments),
                int(record.shares),
                int(record.saves),
                int(record.dislikes),
                float(record.engagement_rate),
                int(record.engagement_total),
                float(record.like_rate),
                float(record.dislike_rate),
                float(record.engagement_per_1k),
                float(record.engagement_like_rate),
                float(record.engagement_comment_rate),
                float(record.engagement_share_rate),
                float(record.avg_watch_time_sec),
                float(record.completion_rate),
                record.publish_date_approx,
                record.year_month,
                record.publish_dayofweek,
                record.publish_period,
                record.event_season,
                record.season,
                int(record.week_of_year),
                country_id,
                author_id,
                device_id,
                trend_id,
            )
        )

        for tag in record.tags_list:
            tag_rows.append((record.row_id, tag))

        if record.sample_comment_clean:
            comment_rows.append((record.row_id, record.sample_comment_clean))

    conn.executemany(
        """
        INSERT INTO Content (
            content_id, platform, category, hashtag, title, title_keywords, title_length,
            has_emoji, duration_sec, views, likes, comments, shares, saves, dislikes,
            engagement_rate, engagement_total, like_rate, dislike_rate, engagement_per_1k,
            engagement_like_rate, engagement_comment_rate, engagement_share_rate,
            avg_watch_time_sec, completion_rate, publish_date_approx, year_month,
            publish_dayofweek, publish_period, event_season, season, week_of_year,
            country_id, author_id, device_id, trend_id
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        content_rows,
    )
    if tag_rows:
        conn.executemany(
            "INSERT INTO Content_Tags (content_id, tag) VALUES (?, ?)",
            tag_rows,
        )
    if comment_rows:
        conn.executemany(
            "INSERT INTO Content_Comments (content_id, sample_comment) VALUES (?, ?)",
            comment_rows,
        )

    return len(content_rows), len(tag_rows), len(comment_rows)


def reseed_database(df: pd.DataFrame) -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found: {DB_PATH}")

    backup_path = backup_database(DB_PATH)
    print(f"[info] Database backup saved to {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = OFF;")
        clear_existing_tables(conn)
        conn.execute("PRAGMA foreign_keys = ON;")

        country_map = seed_countries(conn, df)
        print(f"[info] Inserted {len(country_map)} countries")

        author_map = seed_authors(conn, df)
        print(f"[info] Inserted {len(author_map)} authors")

        device_map = seed_devices(conn, df)
        print(f"[info] Inserted {len(device_map)} device variants")

        trend_map = seed_trends(conn, df)
        print(f"[info] Inserted {len(trend_map)} trend archetypes")

        content_count, tag_count, comment_count = insert_content_and_related(
            conn, df, country_map, author_map, device_map, trend_map
        )
        print(f"[info] Inserted {content_count} content rows, {tag_count} tags, {comment_count} sample comments")

        conn.commit()
        print("[success] Database reseeded successfully.")
    except Exception:
        conn.rollback()
        print("[error] Reseed failed; rolling back changes.")
        raise
    finally:
        conn.close()


def main() -> None:
    df = load_and_clean_dataframe(CSV_PATH)
    print(f"[info] Cleaned dataframe contains {len(df):,} rows.")
    reseed_database(df)


if __name__ == "__main__":
    main()

