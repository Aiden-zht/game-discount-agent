#!/usr/bin/env python3
"""Phase 2: Publish — reads state JSON from Phase 1, creates WeChat draft.

Usage: python3 publish_draft.py <state_file.json>
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_publisher import get_access_token, create_draft, Article

logger = logging.getLogger("publish_draft")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if len(sys.argv) < 2:
        logger.error("Usage: python3 publish_draft.py <state_file.json>")
        return 1

    state_path = sys.argv[1]
    if not os.path.isfile(state_path):
        logger.error(f"State file not found: {state_path}")
        return 1

    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    logger.info(f"Loaded state: {state['game_count']} games, generated at {state['generated_at']}")

    # Read HTML content
    html_path = state["html_path"]
    if not os.path.isfile(html_path):
        logger.error(f"HTML file not found: {html_path}")
        return 1

    with open(html_path, "r", encoding="utf-8") as f:
        article_html = f.read()

    # Create WeChat draft
    logger.info("Creating WeChat draft...")

    article = Article(
        title=state["article_title"],
        content=article_html,
        thumb_media_id=state["thumb_media_id"],
    )
    media_id = create_draft(article)

    if media_id:
        logger.info(f"✅ Draft created! media_id={media_id[:30]}...")
        print(f"DRAFT_CREATED:{media_id}")
        return 0
    else:
        logger.error("❌ Draft creation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
