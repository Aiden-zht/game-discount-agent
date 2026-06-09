"""
Epic Games 免费游戏爬虫

每周四晚 Epic 更新免费游戏，这是国内玩家最关注的内容之一。
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional
import httpx
from bs4 import BeautifulSoup

# 确保独立运行时能找到 steam_scraper
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

from steam_scraper import GameDeal

logger = logging.getLogger(__name__)

RETRY_MAX = 3
RETRY_BACKOFF = 2.0


class EpicScraper:
    """Epic 商城免费游戏抓取"""

    def __init__(self, timeout: int = 15):
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/120.0.0.0 Safari/537.36"),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._client.close()

    def get_free_games(self) -> list[GameDeal]:
        """获取 Epic 本周免费游戏"""
        # Epic 免费游戏页面
        url = "https://store.epicgames.com/zh-CN/free-games"

        last_exc = None
        for attempt in range(1, RETRY_MAX + 1):
            try:
                resp = self._client.get(url)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "lxml")
                deals = []

                # Epic 前端是 React SSR，title 通常在 meta 或特定 class 里
                # 用更通用的方式提取
                script_data = soup.find("script", {"id": "__NEXT_DATA__"})
                if script_data:
                    data = json.loads(script_data.string)
                    deals = self._parse_from_next_data(data)
                    if deals:
                        return deals

                # 备用：从页面元素提取
                for card in soup.select('[class*="card"], [class*="offer"]')[:10]:
                    title_tag = card.select_one("h3, h4, [class*='title']")
                    if not title_tag:
                        continue
                    title = title_tag.text.strip()
                    if not title:
                        continue

                    deals.append(GameDeal(
                        appid=0,
                        name=title,
                        source="epic_free",
                        store_url="https://store.epicgames.com/zh-CN/free-games",
                        fetched_at=datetime.now(timezone.utc).isoformat(),
                    ))
                return deals

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < RETRY_MAX:
                    wait = RETRY_BACKOFF ** attempt
                    logger.warning(f"Epic 第 {attempt} 次失败，{wait:.0f}s 后重试: {e}")
                    time.sleep(wait)

        logger.error(f"Epic 重试 {RETRY_MAX} 次后仍失败: {last_exc}")
        return []

    def _parse_from_next_data(self, data: dict) -> list[GameDeal]:
        """从 Epic 的 __NEXT_DATA__ JSON 中解析免费游戏"""
        deals = []
        try:
            # 遍历嵌套查找免费游戏数据
            pages = data.get("props", {}).get("pageProps", {})
            offers = pages.get("offer", []) or pages.get("offers", [])
            if not offers:
                # 可能在其他位置
                for key, val in pages.items():
                    if isinstance(val, list) and len(val) > 0:
                        offers = val
                        break

            for offer in offers[:10]:
                if isinstance(offer, dict):
                    title = offer.get("title", offer.get("name", ""))
                    if title:
                        deals.append(GameDeal(
                            appid=offer.get("id", 0),
                            name=title,
                            source="epic_free",
                            header_image=offer.get("keyImages", [{}])[0].get("url", "") if offer.get("keyImages") else "",
                            store_url="https://store.epicgames.com/zh-CN/free-games",
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                        ))
        except Exception as e:
            logger.warning(f"解析 Epic __NEXT_DATA__ 失败: {e}")

        return deals


def main():
    """测试"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    with EpicScraper() as scraper:
        print("=== Epic 本周免费 ===")
        deals = scraper.get_free_games()
        if deals:
            for d in deals:
                print(f"  {d.name}")
        else:
            print("  当前未获取到免费游戏（可能不是更新日）")
        print(f"\n共 {len(deals)} 个")


if __name__ == "__main__":
    main()
