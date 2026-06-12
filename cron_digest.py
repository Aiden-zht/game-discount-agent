#!/usr/bin/env python3
"""Daily game digest pipeline — Phase 1: Build article assets.

Scrapes Steam deals, uploads images to WeChat CDN, generates HTML,
uploads cover thumb. Saves all state to JSON for Phase 2 validation + publish.
"""

import json
import logging
import os
import random
import sys
from datetime import datetime

# Steam API 翻墙走本地 mihomo SOCKS5，微信 API 直连走代理=0（不通代理）
# ⚠️ 绝对不能设全局 HTTP_PROXY/HTTPS_PROXY，否则微信请求也会走代理烧钱
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
STEAM_PROXY = "socks5://127.0.0.1:7891"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx

from steam_scraper import SteamScraper
from content_generator import ArticleGenerator
from image_uploader import WeChatImageUploader
from wechat_publisher import get_access_token, upload_image_thumb, ensure_thumb

logger = logging.getLogger("cron_digest")

# State file path
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def _serialize_deal(d, image_map=None) -> dict:
    """Convert a GameDeal object to a JSON-serializable dict."""
    if image_map is None:
        image_map = {}
    result = {
        "appid": d.appid,
        "name": d.name,
        "name_en": d.name_en or "",
        "name_cn": d.name_cn or "",
        "discount_percent": d.discount_percent,
        "final_price": d.final_price,
        "final_price_cents": d.final_price_cents,
        "original_price": d.original_price,
        "original_price_cents": d.original_price_cents,
        "review_score": d.review_score,
        "review_desc": d.review_desc or "",
        "is_dlc": d.is_dlc,
        "header_image": getattr(d, "header_image", "") or "",
    }
    # Inject WeChat CDN cover URL if available
    cover_url = image_map.get(d.appid, "")
    result["cover_url"] = cover_url
    return result


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("=== Steam Discount Daily Digest Phase 1 ===")
    logger.info("Step 1/4: Scraping Steam deals...")

    # --- Step 1: Scrape (Steam needs proxy, WeChat must not) ---
    with SteamScraper(timeout=30, proxy=STEAM_PROXY) as scraper:
        deals = scraper.get_deals()

    logger.info(f"Found {len(deals)} deals")

    if not deals:
        logger.warning("No deals found, aborting.")
        return 1

    # Dedup by appid
    seen = set()
    unique = []
    for d in sorted(deals, key=lambda x: x.discount_percent, reverse=True):
        if d.appid not in seen:
            seen.add(d.appid)
            unique.append(d)

    logger.info(f"Unique deals: {len(unique)}")

    # --- Step 2: Upload images to WeChat CDN ---
    logger.info("Step 2/4: Uploading game images to WeChat CDN...")

    token = get_access_token()
    logger.info("WeChat token obtained")

    image_map = {}
    with WeChatImageUploader(proxy=STEAM_PROXY) as uploader:
        image_map = uploader.process_game_images(unique, token)

    success_count = sum(1 for v in image_map.values() if "mmbiz.qpic.cn" in v)
    logger.info(f"Images uploaded: {success_count}/{len(unique)}")

    # Filter out games with no WeChat CDN image (spec 4.3: no image = remove from recommendation)
    no_image = [d for d in unique if d.appid not in image_map or not image_map.get(d.appid, "").strip()]
    if no_image:
        logger.info(f"Removing {len(no_image)} games with no image per spec 4.3:")
        for d in no_image:
            logger.info(f"  - {d.name} (appid {d.appid})")
    unique = [d for d in unique if d.appid in image_map and image_map[d.appid].strip()]
    logger.info(f"After image filter: {len(unique)} games (removed {len(no_image)})")

    # --- Step 3: Pick most popular game for cover thumb ---
    logger.info("Step 3/4: Uploading cover thumb...")

    best = max(unique, key=lambda d: (d.review_score, d.discount_percent))
    logger.info(f"Cover game: {best.name} (好评 {best.review_score}% · -{best.discount_percent}%)")

    cover_url = getattr(best, "header_image", "") or \
                f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{best.appid}/header.jpg"

    thumb_media_id = ""
    with httpx.Client(timeout=30) as client:
        token = get_access_token()  # refresh token (may have expired during upload)
        try:
            thumb_media_id = upload_image_thumb(client, token, cover_url)
            logger.info(f"Cover thumb: {thumb_media_id[:20]}...")
        except Exception as e:
            logger.warning(f"Cover thumb upload failed: {e}, falling back to default")
            thumb_media_id = ensure_thumb()

    # --- Step 4: Generate article HTML ---
    logger.info("Step 4/4: Generating rich article...")

    # Generate a short version ID: YYMMDD + 6 random hex chars
    # Visible in article footer for easy session/agent identification
    today_short = datetime.now().strftime("%y%m%d")
    rand_hex = f"{random.randint(0, 0xFFFFFF):06x}"
    version_id = f"{today_short}-{rand_hex}"
    logger.info(f"Version ID: V{version_id}")

    generator = ArticleGenerator()
    article_html = generator.generate_daily_digest(unique, [], image_map=image_map, version_id=version_id)

    os.makedirs(STATE_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    html_path = os.path.join(STATE_DIR, f"digest_{today}_rich.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(article_html)
    logger.info(f"Article saved: {html_path} ({len(article_html)} chars)")

    # --- Save state file for Phase 2 ---
    title = f"Steam 今日特惠 {datetime.now().strftime('%m/%d')}"

    state = {
        "generated_at": datetime.now().isoformat(),
        "article_title": title,
        "html_path": html_path,
        "html_length": len(article_html),
        "cover_appid": best.appid,
        "thumb_media_id": thumb_media_id,
        "image_map": image_map,
        "games": [_serialize_deal(d, image_map) for d in unique],
        "game_count": len(unique),
        "image_upload_count": success_count,
        "version_id": version_id,
    }

    state_path = os.path.join(STATE_DIR, f"state_{today}.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    logger.info(f"State saved: {state_path}")

    # Output summary to stdout (cron will capture this)
    print(f"✅ Phase 1 complete: {len(unique)} games, {success_count} images, {len(article_html)} chars")
    print(f"📄 State file: {state_path}")
    print(f"📄 HTML file: {html_path}")
    print(f"📸 Cover thumb: {thumb_media_id[:30]}...")

    return 0


def _fallback_thumb() -> str:
    """Fallback: use default generated thumb when cover upload fails."""
    from wechat_publisher import ensure_thumb
    return ensure_thumb()


if __name__ == "__main__":
    sys.exit(main())
