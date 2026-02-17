"""Orchestrator: ingest + diff (single entry point)."""

import logging
import sys
from datetime import date, timedelta

from diff import run_diff
from ingest import ingest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    # Accept optional date argument for backfilling
    if len(sys.argv) > 1:
        try:
            target_date = date.fromisoformat(sys.argv[1])
        except ValueError:
            logger.error("Invalid date format: %s (expected YYYY-MM-DD)", sys.argv[1])
            sys.exit(1)
    else:
        target_date = date.today()

    yesterday = target_date - timedelta(days=1)

    logger.info("Pipeline start — target date: %s", target_date.isoformat())

    # Step 1: Ingest
    try:
        df = ingest(target_date)
        logger.info("Ingested %d total posts", len(df))
    except Exception:
        logger.exception("Ingestion failed")
        sys.exit(1)

    # Step 2: Diff
    new_count = run_diff(target_date, yesterday)
    logger.info("%d new posts found", new_count)

    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
