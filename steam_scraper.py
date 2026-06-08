"""
Steam 折扣/特惠爬虫

抓取 Steam 当前特惠游戏列表，包括折扣率、价格、好评率等信息。
使用 Steam Store API（官方接口，无需 token）。

用法:
    scraper = SteamScraper()
    with scraper:
        deals = scraper.get_deals()
        for d in deals:
            print(f"{d.name} - {d.discount_percent}% off")
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


# 国内访问 Steam 经常超时，重试参数
RETRY_MAX = 3
RETRY_BACKOFF = 2.0  # 每次翻倍


@dataclass
class GameDeal:
    """统一的游戏折扣数据结构"""
    appid: int
    name: str
    original_price_cents: int = 0
    final_price_cents: int = 0
    discount_percent: int = 0
    currency: str = "CNY"
    review_score: int = 0
    review_desc: str = ""
    header_image: str = ""
    store_url: str = ""
    source: str = "steam"  # steam / steam_free
    fetched_at: str = ""

    @property
    def original_price(self) -> str:
        if self.original_price_cents <= 0:
            return "免费"
        return f"¥{self.original_price_cents / 100:.2f}"

    @property
    def final_price(self) -> str:
        if self.final_price_cents <= 0:
            return "免费"
        return f"¥{self.final_price_cents / 100:.2f}"

    @property
    def is_free(self) -> bool:
        return self.final_price_cents <= 0

    def to_dict(self) -> dict:
        return {
            "appid": self.appid,
            "name": self.name,
            "original_price": self.original_price,
            "original_price_cents": self.original_price_cents,
            "final_price": self.final_price,
            "final_price_cents": self.final_price_cents,
            "discount_percent": self.discount_percent,
            "currency": self.currency,
            "review_score": self.review_score,
            "review_desc": self.review_desc,
            "header_image": self.header_image,
            "store_url": self.store_url,
            "source": self.source,
            "fetched_at": self.fetched_at,
        }


class SteamScraper:
    """Steam 商店折扣数据抓取器"""

    API_BASE = "https://store.steampowered.com/api"
    STORE_URL = "https://store.steampowered.com"

    def __init__(self, timeout: int = 15):
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/html",
            },
            follow_redirects=True,
        )
        self._featured_cache: Optional[dict] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self._client.close()

    # ------------------------------------------------------------------
    # 核心 API 请求（带缓存，避免重复请求）
    # ------------------------------------------------------------------

    def _fetch_featured(self) -> dict:
        """获取 /api/featuredcategories 数据，带缓存 + 自动重试"""
        if self._featured_cache is not None:
            return self._featured_cache

        last_exc = None
        for attempt in range(1, RETRY_MAX + 1):
            try:
                url = f"{self.API_BASE}/featuredcategories"
                resp = self._client.get(url, params={"l": "schinese", "cc": "CN"})
                resp.raise_for_status()
                self._featured_cache = resp.json()
                return self._featured_cache
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < RETRY_MAX:
                    wait = RETRY_BACKOFF ** attempt
                    logger.warning(f"Steam API 第 {attempt} 次失败，{wait:.0f}s 后重试: {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"Steam API 重试 {RETRY_MAX} 次后仍失败: {e}")

        raise last_exc  # 让调用方处理

    # ------------------------------------------------------------------
    # 特惠游戏
    # ------------------------------------------------------------------

    def get_deals(self) -> list[GameDeal]:
        """获取 Steam 当前特惠游戏"""
        try:
            data = self._fetch_featured()
            items = data.get("specials", {}).get("items", [])
            return [self._api_item_to_deal(item) for item in items]
        except httpx.HTTPStatusError as e:
            logger.error(f"Steam API HTTP {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Steam API 连接失败: {e}")
            return []
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Steam API 数据解析异常: {e}")
            return []

    def get_top_sellers(self) -> list[GameDeal]:
        """获取 Steam 热销榜"""
        try:
            data = self._fetch_featured()  # 共享缓存，不重复请求
            items = data.get("top_sellers", {}).get("items", [])
            return [self._api_item_to_deal(item) for item in items]
        except httpx.HTTPStatusError as e:
            logger.error(f"Steam API HTTP {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Steam API 连接失败: {e}")
            return []
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Steam API 数据解析异常: {e}")
            return []

    # ------------------------------------------------------------------
    # 搜索更多特惠（覆盖面更广的 HTML 页面）
    # ------------------------------------------------------------------

    def search_specials(self, limit: int = 30) -> list[GameDeal]:
        """通过搜索页面获取更多特惠游戏（比 API 覆盖面更广）"""
        from bs4 import BeautifulSoup

        url = f"{self.STORE_URL}/search/"
        params = {
            "specials": "1",
            "filter": "globaltopsellers",
            "l": "schinese",
            "cc": "CN",
            "num_per_page": str(min(limit, 50)),
        }

        last_exc = None
        for attempt in range(1, RETRY_MAX + 1):
            try:
                resp = self._client.get(url, params=params)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "lxml")
                deals = []
                for row in soup.select("a.search_result_row")[:limit]:
                    deal = self._parse_search_row(row)
                    if deal:
                        deals.append(deal)
                return deals

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < RETRY_MAX:
                    wait = RETRY_BACKOFF ** attempt
                    logger.warning(f"Steam search 第 {attempt} 次失败，{wait:.0f}s 后重试: {e}")
                    time.sleep(wait)

        logger.error(f"Steam search 重试 {RETRY_MAX} 次后仍失败: {last_exc}")
        return []

    # ------------------------------------------------------------------
    # 免费游戏
    # ------------------------------------------------------------------
    def get_free_games(self) -> list[GameDeal]:
        """获取 Steam 免费游戏（含永久免费/限免）"""
        from bs4 import BeautifulSoup

        url = f"{self.STORE_URL}/search/"
        params = {
            "maxprice": "free",
            "category1": "998",
            "l": "schinese",
            "cc": "CN",
        }

        last_exc = None
        for attempt in range(1, RETRY_MAX + 1):
            try:
                resp = self._client.get(url, params=params)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "lxml")
                deals = []
                for row in soup.select("a.search_result_row")[:10]:
                    name_tag = row.select_one("span.title")
                    name = name_tag.text.strip() if name_tag else ""
                    appid_str = row.get("data-ds-appid", "0")
                    appid = int(appid_str.split(",")[0]) if appid_str and appid_str.split(",")[0].isdigit() else 0

                    if appid == 0:
                        logger.debug(f"跳过无法解析 appid 的免费游戏: {name}")
                        continue

                    deals.append(GameDeal(
                        appid=appid,
                        name=name,
                        source="steam_free",
                        header_image=f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
                        store_url=f"https://store.steampowered.com/app/{appid}/",
                        fetched_at=datetime.now(timezone.utc).isoformat(),
                    ))
                return deals

            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < RETRY_MAX:
                    wait = RETRY_BACKOFF ** attempt
                    logger.warning(f"Free games 第 {attempt} 次失败，{wait:.0f}s 后重试: {e}")
                    time.sleep(wait)

        logger.error(f"Free games 重试 {RETRY_MAX} 次后仍失败: {last_exc}")
        return []

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _api_item_to_deal(self, item: dict) -> GameDeal:
        """将 API 返回的 item 转为统一 GameDeal"""
        return GameDeal(
            appid=item.get("id", 0),
            name=item.get("name", ""),
            original_price_cents=item.get("original_price", 0),
            final_price_cents=item.get("final_price", 0),
            discount_percent=item.get("discount_percent", 0),
            review_score=item.get("review_score", 0),
            review_desc=item.get("review_desc", ""),
            header_image=f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{item.get('id', 0)}/header.jpg",
            store_url=f"https://store.steampowered.com/app/{item.get('id', 0)}/",
            source="steam",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def _parse_search_row(self, row) -> Optional[GameDeal]:
        """解析搜索页面上的一行游戏"""
        try:
            appid_str = row.get("data-ds-appid", "0")
            appid = int(appid_str) if appid_str.isdigit() else 0
            name_tag = row.select_one("span.title")
            name = name_tag.text.strip() if name_tag else ""

            discount_pct = row.select_one("div.discount_pct")
            discount = int(discount_pct.text.replace("-", "").replace("%", "")) if discount_pct else 0

            if discount <= 0:
                logger.debug(f"跳过无折扣游戏: {name}")
                return None

            # 解析价格文本（搜索页价格是字符串如 "¥32.40"）
            final_price_tag = row.select_one("div.discount_final_price")
            original_price_tag = row.select_one("div.discount_original_price")

            final_price_str = final_price_tag.text.strip() if final_price_tag else ""
            original_price_str = original_price_tag.text.strip() if original_price_tag else ""

            # 尝试从价格字符串解析数值（分）
            def parse_cents(price_str: str) -> int:
                import re
                m = re.search(r"[\d.]+$", price_str.replace("¥", ""))
                return int(float(m.group()) * 100) if m else 0

            return GameDeal(
                appid=appid,
                name=name,
                discount_percent=discount,
                original_price_cents=parse_cents(original_price_str),
                final_price_cents=parse_cents(final_price_str),
                header_image=f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
                store_url=f"https://store.steampowered.com/app/{appid}/",
                source="steam",
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.debug(f"解析 search_row 失败: {e}")
            return None


def main():
    """测试"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    with SteamScraper() as scraper:
        print("=== Steam 特惠游戏 ===")
        deals = scraper.get_deals()
        for d in deals[:15]:
            print(f"  {d.name:40s} | 原价 {d.original_price:>8s} | 现价 {d.final_price:>8s} | -{d.discount_percent}%")
        print(f"\n共 {len(deals)} 个特惠游戏\n")

        print("=== Steam 热销榜 ===")
        top = scraper.get_top_sellers()
        for d in top[:10]:
            tag = f"-{d.discount_percent}%" if d.discount_percent else "无折扣"
            print(f"  {d.name:40s} | {tag:>8s}")
        print(f"\n共 {len(top)} 个热销游戏")


if __name__ == "__main__":
    main()
