"""Orchestrator: fetch + filter + analyze (single entry point)."""

import logging
import os
import sys

import litellm
import pandas as pd

from ttsfeed.analyze import analyze_posts
from ttsfeed.config import enriched_output_path, raw_output_path
from ttsfeed.export import _post_to_dict, save_output
from ttsfeed.fetch import bytes_to_dataframe, download_archive, filter_recent_posts

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
    logger.info("%d new posts found", len(new_posts_df))
    reference_time = pd.Timestamp.now("UTC")
    raw_path = raw_output_path(reference_time.date())
    enriched_path = enriched_output_path(reference_time.date())

    save_output(
        new_posts_df,
        total_archive=len(df),
        reference_time=reference_time,
        output_dir=raw_path.parent,
        output_name=raw_path.name,
    )

    llm_model = os.environ.get("LLM_MODEL")
    if llm_model:
        posts = [_post_to_dict(row) for _, row in new_posts_df.iterrows()]

        def complete(prompt: str) -> str:
            response = litellm.completion(
                model=llm_model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""

        try:
            enrichment = analyze_posts(posts, complete)
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
        except Exception:
            logger.warning("LLM enrichment failed; skipping", exc_info=True)
    else:
        logger.info("LLM_MODEL not set; skipping enrichment")

    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
