"""Orchestrator: fetch + filter + analyze (single entry point)."""

import json
import logging
import os
import sys
from datetime import date

import pandas as pd

from ttsfeed.analyze import analyze_posts
from ttsfeed.config import (
    LLM_MODELS,
    LLM_PROVIDER,
    enriched_output_path,
    log_output_path,
    raw_output_path,
)
from ttsfeed.export import _post_to_dict, save_output
from ttsfeed.fetch import bytes_to_dataframe, download_archive, filter_recent_posts
from ttsfeed.llm import build_complete_fn
from ttsfeed.notify import send_notification

_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _write_run_summary(
    run_date: date,
    t0: pd.Timestamp,
    t1: pd.Timestamp,
    status: str,
    fetch_info: dict,
    enrichment_info: dict,
    notification_info: dict,
    output_files: dict,
) -> None:
    """Write the daily run summary JSON to data/logs/YYYY-MM-DD.json."""
    path = log_output_path(run_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_date": run_date.isoformat(),
        "run_started_at": t0.isoformat(),
        "run_finished_at": t1.isoformat(),
        "duration_seconds": round((t1 - t0).total_seconds(), 1),
        "status": status,
        "fetch": fetch_info,
        "enrichment": enrichment_info,
        "notification": notification_info,
        "output_files": output_files,
    }
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info("Run summary written: %s", path)


def main() -> None:
    t0 = pd.Timestamp.now("UTC")
    logger.info("Pipeline start")

    try:
        raw = download_archive()
        df = bytes_to_dataframe(raw)
        logger.info("Fetched %d total posts", len(df))
    except Exception:
        logger.exception("Fetch failed")
        sys.exit(1)

    new_posts_df = filter_recent_posts(df)
    logger.info("%d new posts found", len(new_posts_df))
    reference_time = pd.Timestamp.now("UTC")
    run_date = reference_time.date()
    raw_path = raw_output_path(run_date)
    enriched_path = enriched_output_path(run_date)
    logger.info("Run date: %s", run_date)

    save_output(
        new_posts_df,
        total_archive=len(df),
        reference_time=reference_time,
        output_dir=raw_path.parent,
        output_name=raw_path.name,
    )
    logger.info("Raw output: %s", raw_path)

    fetch_info: dict = {
        "total_posts_in_archive": len(df),
        "new_posts_count": len(new_posts_df),
    }

    new_posts = [_post_to_dict(row) for _, row in new_posts_df.iterrows()]
    enrichment = None
    enrichment_error: str | None = None

    complete = build_complete_fn()
    enrichment_attempted = complete is not None
    if complete is not None:
        try:
            enrichment = analyze_posts(new_posts, complete)
            logger.info(
                "Enrichment complete: %d categorized posts",
                len(enrichment.post_categories),
            )
            save_output(
                new_posts_df,
                total_archive=len(df),
                reference_time=reference_time,
                enrichment=enrichment,
                output_dir=enriched_path.parent,
                output_name=enriched_path.name,
            )
            logger.info("Enriched output: %s", enriched_path)
        except Exception as exc:
            logger.warning("LLM enrichment failed; skipping", exc_info=True)
            enrichment_error = str(exc)
    else:
        logger.info("No LLM provider available; skipping enrichment")

    enrichment_info: dict = {
        "attempted": enrichment_attempted,
        "provider": LLM_PROVIDER,
        "model": LLM_MODELS[0] if LLM_MODELS else None,
        "succeeded": enrichment is not None,
        "posts_categorized": len(enrichment.post_categories) if enrichment else 0,
        "error": enrichment_error,
    }

    notif_ok = send_notification(reference_time, new_posts, enrichment)
    notification_info: dict = {
        "attempted": True,
        "succeeded": notif_ok,
        "error": None if notif_ok else "email send failed (see logs)",
    }

    status = "success"
    if enrichment_attempted and not enrichment_info["succeeded"]:
        status = "partial"
    if not notif_ok:
        status = "partial"

    output_files: dict = {
        "raw": str(raw_path),
        "enriched": str(enriched_path) if enrichment is not None else None,
    }

    t1 = pd.Timestamp.now("UTC")
    elapsed = (t1 - t0).total_seconds()
    logger.info("Pipeline complete in %.1f seconds", elapsed)

    _write_run_summary(
        run_date=run_date,
        t0=t0,
        t1=t1,
        status=status,
        fetch_info=fetch_info,
        enrichment_info=enrichment_info,
        notification_info=notification_info,
        output_files=output_files,
    )


if __name__ == "__main__":
    main()
