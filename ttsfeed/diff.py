"""Extract new posts by comparing daily snapshots."""

import json
import logging
from datetime import date

import pandas as pd

from ttsfeed.config import DIFFS_DIR, diff_path, snapshot_path

logger = logging.getLogger(__name__)


def load_snapshot(d: date) -> pd.DataFrame | None:
    """Read a Parquet snapshot for the given date. Returns None if missing."""
    path = snapshot_path(d)
    if not path.exists():
        logger.warning("Snapshot not found: %s", path.name)
        return None
    df = pd.read_parquet(path)
    if "id" in df.columns:
        df["id"] = df["id"].astype(str)
    return df


def find_new_posts(today_df: pd.DataFrame, yesterday_df: pd.DataFrame) -> pd.DataFrame:
    """Return rows from today_df whose id is not in yesterday_df."""
    yesterday_ids = set(yesterday_df["id"])
    new_mask = ~today_df["id"].isin(yesterday_ids)
    return today_df[new_mask].copy()


def _post_to_dict(row: pd.Series) -> dict:
    """Convert a DataFrame row to the output dict format."""
    media = []
    if "media_attachments" in row.index and row["media_attachments"] is not None:
        val = row["media_attachments"]
        if isinstance(val, list):
            media = val
        elif isinstance(val, str):
            try:
                media = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                media = []

    return {
        "id": str(row.get("id", "")),
        "created_at": str(row.get("created_at", "")),
        "content": str(row.get("content", "")),
        "url": row.get("url", f"https://truthsocial.com/@realDonaldTrump/{row.get('id', '')}"),
        "media": media,
        "replies_count": int(row.get("replies_count", 0)),
        "reblogs_count": int(row.get("reblogs_count", 0)),
        "favourites_count": int(row.get("favourites_count", 0)),
    }


def save_diff(
    new_posts_df: pd.DataFrame,
    today_date: date,
    yesterday_date: date,
    total_today: int,
    total_yesterday: int,
) -> None:
    """Write the diff result to a JSON file."""
    DIFFS_DIR.mkdir(parents=True, exist_ok=True)

    new_posts = [_post_to_dict(row) for _, row in new_posts_df.iterrows()]

    result = {
        "date_from": yesterday_date.isoformat(),
        "date_to": today_date.isoformat(),
        "summary": {
            "total_posts_today": total_today,
            "total_posts_yesterday": total_yesterday,
            "new_posts_count": len(new_posts),
        },
        "new_posts": new_posts,
    }

    path = diff_path(today_date)
    with open(path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Saved diff: %s (%d new posts)", path.name, len(new_posts))


def run_diff(today_date: date, yesterday_date: date) -> int:
    """Load snapshots, find new posts, save diff. Returns count of new posts.

    Returns 0 and skips gracefully if yesterday's snapshot is missing (first run).
    """
    today_df = load_snapshot(today_date)
    if today_df is None:
        logger.error("Today's snapshot missing — cannot compute diff")
        return 0

    yesterday_df = load_snapshot(yesterday_date)
    if yesterday_df is None:
        logger.info("No previous snapshot found (first run?) — skipping diff")
        return 0

    new_posts_df = find_new_posts(today_df, yesterday_df)

    save_diff(
        new_posts_df,
        today_date=today_date,
        yesterday_date=yesterday_date,
        total_today=len(today_df),
        total_yesterday=len(yesterday_df),
    )

    return len(new_posts_df)
