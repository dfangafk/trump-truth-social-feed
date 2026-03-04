"""Orchestrator: fetch + filter + analyze (single entry point)."""

import logging
import sys

import pandas as pd

from ttsfeed.analyze import analyze_posts
from ttsfeed.config import settings
from ttsfeed.export import post_to_dict, save_output
from ttsfeed.fetch import bytes_to_dataframe, download_archive, filter_recent_posts
from ttsfeed.llm import build_complete_fn
from ttsfeed.notify import NotifyFn, send_notification

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_log_level = getattr(logging, settings.pipeline.log_level.upper(), logging.INFO)
logging.basicConfig(level=_log_level, format=_LOG_FORMAT)
logger = logging.getLogger(__name__)


def _add_file_handler(run_date) -> None:
    """Attach a date-stamped FileHandler to the root logger."""
    settings.paths.logs_output_dir.mkdir(parents=True, exist_ok=True)
    log_file = settings.paths.logs_output_dir / f"{run_date.isoformat()}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logging.getLogger().addHandler(file_handler)


def main(notify_fn: NotifyFn | None = None) -> None:
    t0 = pd.Timestamp.now("UTC")
    run_date = t0.date()
    _add_file_handler(run_date)
    logger.info("Pipeline start")

    try:
        raw = download_archive()
        df = bytes_to_dataframe(raw)
        logger.info("Fetched %d total posts", len(df))
    except Exception:
        logger.exception("Fetch failed")
        sys.exit(1)

    new_posts_df = filter_recent_posts(df, hours=settings.pipeline.hours)
    logger.info("%d new posts found", len(new_posts_df))
    reference_time = pd.Timestamp.now("UTC")
    raw_path = settings.paths.raw_output_dir / f"{run_date.isoformat()}.json"
    enriched_path = settings.paths.enriched_output_dir / f"{run_date.isoformat()}.json"
    logger.info("Run date: %s", run_date)

    save_output(
        new_posts_df,
        total_archive=len(df),
        reference_time=reference_time,
        output_path=raw_path,
    )

    new_posts = [post_to_dict(row) for _, row in new_posts_df.iterrows()]
    enrichment = None

    complete = build_complete_fn()
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
                output_path=enriched_path,
            )

        except Exception:
            logger.warning("LLM enrichment failed; skipping", exc_info=True)
    else:
        logger.info("No LLM provider available; skipping enrichment")

    elapsed = (pd.Timestamp.now("UTC") - t0).total_seconds()
    logger.info("Pipeline complete in %.1f seconds", elapsed)

    notifier = notify_fn if notify_fn is not None else send_notification
    notifier(reference_time, new_posts, enrichment)


if __name__ == "__main__":
    main()
