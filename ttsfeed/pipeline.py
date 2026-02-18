"""Orchestrator: fetch + filter (single entry point)."""

import logging
import sys

from ttsfeed.fetch import bytes_to_dataframe, download_archive
from ttsfeed.filter import filter_recent_posts, save_output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Pipeline start")

    try:
        raw, fmt = download_archive()
        df = bytes_to_dataframe(raw, fmt)
        logger.info("Fetched %d total posts", len(df))
    except Exception:
        logger.exception("Fetch failed")
        sys.exit(1)

    new_posts_df = filter_recent_posts(df)
    save_output(new_posts_df, total_archive=len(df))
    logger.info("%d new posts found", len(new_posts_df))

    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
