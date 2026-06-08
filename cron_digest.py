#!/usr/bin/env python3
"""Daily game digest pipeline.

Full pipeline:
1. Scrape Steam deals
2. Upload game images to WeChat CDN
3. Generate rich HTML article
4. Create WeChat draft
"""

import logging
import os
import sys

# Ensure proxy is set
os.environ.setdefault("HTTP_PROXY", "http://192.168.0.196:7890")
os.environ.setdefault("HTTPS_PROXY", "http://192.168.0.196:7890")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from steam_scraper import SteamScraper
from content_generator import ArticleGenerator
from image_uploader import WeChatImageUploader
from wechat_publisher import get_access_token, create_draft, ensure_thumb, Article

logger = logging.getLogger("cron_digest")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=== Steam Discount Daily Digest ===")
    logger.info("Step 1/4: Scraping Steam deals...")

    # --- Step 1: Scrape ---
    with SteamScraper(timeout=30) as scraper:
        deals = scraper.get_deals()

    logger.info(f"Found {len(deals)} deals")

    if not deals:
        logger.warning("No deals found, aborting.")
        return 1

    # --- Step 2: Upload images to WeChat CDN ---
    logger.info("Step 2/4: Uploading game images to WeChat CDN...")

    # Dedup by appid first
    seen = set()
    unique = []
    for d in sorted(deals, key=lambda x: x.discount_percent, reverse=True):
        if d.appid not in seen:
            seen.add(d.appid)
            unique.append(d)

    logger.info(f"Unique deals: {len(unique)}")

    token = get_access_token()
    logger.info(f"WeChat token obtained: {token[:15]}...")

    image_map = {}
    with WeChatImageUploader() as uploader:
        image_map = uploader.process_game_images(unique, token)

    success_count = sum(1 for v in image_map.values() if "mmbiz.qpic.cn" in v)
    logger.info(f"Images uploaded: {success_count}/{len(unique)}")

    # --- Step 3: Generate article ---
    logger.info("Step 3/4: Generating rich article...")

    generator = ArticleGenerator()
    article_html = generator.generate_daily_digest(unique, [], image_map=image_map)

    output_path = os.path.join(
        os.path.dirname(__file__),
        "output",
        f"digest_{datetime.now().strftime('%Y%m%d')}_rich.html",
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(article_html)

    logger.info(f"Article saved: {output_path} ({len(article_html)} chars)")

    # --- Step 4: Upload to WeChat draft ---
    logger.info("Step 4/4: Creating WeChat draft...")

    # upload_thumb_to_wechat → ensure_thumb
    thumb_media_id = ensure_thumb()

    logger.info(f"Thumb media_id: {thumb_media_id}")

    # Save draft
    title_content = f"Steam 今日特惠 {datetime.now().strftime('%m/%d')}"
    article = Article(
        title=title_content,
        content=article_html,
        thumb_media_id=thumb_media_id,
    )
    media_id = create_draft(article)

    if media_id:
        logger.info(f"✅ Draft saved! media_id={media_id[:20]}...")
        logger.info("📝 草稿已保存，请去 mp.weixin.qq.com → 草稿箱 → 点发布")
        return 0
    else:
        logger.error("❌ Draft creation failed")
        return 1


if __name__ == "__main__":
    from datetime import datetime
    sys.exit(main())
