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

# DLC/Bundle → 母游戏 appid 映射
PARENT_APPID_MAP: dict[int, int] = {
    736589: 268910,    # Cuphead - The Delicious Last Course → Cuphead
    1313468: 1364780,  # Street Fighter 6 Years 1-2 Fighters Edition → SF6
    692569: 1446780,   # MONSTER HUNTER RISE + SUNBREAK 组合包 → Monster Hunter Rise
}


@dataclass
class GameDeal:
    """统一的游戏折扣数据结构"""
    appid: int
    name: str
    name_en: str = ""
    name_cn: str = ""
    original_price_cents: int = 0
    final_price_cents: int = 0
    discount_percent: int = 0
    currency: str = "CNY"
    review_score: int = 0
    review_desc: str = ""
    is_dlc: bool = False
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

    def _fetch_en_names(self) -> dict[int, str]:
        """获取英文游戏名，返回 {appid: english_name}"""
        try:
            resp = self._client.get(
                f"{self.API_BASE}/featuredcategories",
                params={"l": "english", "cc": "US"},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("specials", {}).get("items", [])
            return {item["id"]: item["name"] for item in items if "id" in item}
        except Exception as e:
            logger.warning(f"获取英文名失败: {e}")
            return {}

    # ------------------------------------------------------------------
    # 特惠游戏
    # ------------------------------------------------------------------

    def get_deals(self) -> list[GameDeal]:
        """获取 Steam 当前特惠游戏（带英文+中文双语名）"""
        try:
            data = self._fetch_featured()
            items = data.get("specials", {}).get("items", [])
            deals = [self._api_item_to_deal(item) for item in items]

            # 并行查询 appdetails + appreviews 获取双语名和好评率
            appids = [d.appid for d in deals if d.appid]
            if appids:
                bilingual = self._fetch_bilingual_names(appids)
                need_translate = []
                for d in deals:
                    if d.appid in bilingual:
                        info = bilingual[d.appid]
                        d.name_en = info["en"]
                        d.name_cn = info["cn"]
                        if info["header_image"]:
                            d.header_image = info["header_image"]
                        if info["review_score"] > 0:
                            d.review_score = info["review_score"]
                            d.review_desc = info["review_desc"]

                # 批量翻译：中文名空缺或中英文相同时，用 DeepSeek 翻译
                for d in deals:
                    en = (d.name_en or d.name).strip()
                    cn = (d.name_cn or "").strip()
                    if en and (not cn or cn == en or cn == "MISSING"):
                        need_translate.append(d)

                if need_translate:
                    # 读 .env 拿 API Key（优先用 day77 中转，和主模型一致）
                    dotenv_path = os.path.expanduser("~/.hermes/.env")
                    api_key = ""
                    api_base = "https://api.day77.icu/v1"
                    if os.path.isfile(dotenv_path):
                        with open(dotenv_path) as f:
                            for line in f:
                                line = line.strip()
                                if "DAY77_API_KEY" in line and "***" not in line:
                                    api_key = line.split("=", 1)[1].strip()
                                    break
                    if not api_key:
                        api_key = os.environ.get("DAY77_API_KEY", os.environ.get("DEEPSEEK_API_KEY", ""))
                    if api_key:
                        names_en = [d.name_en or d.name for d in need_translate]
                        try:
                            prompt = f"翻译以下Steam游戏名成简体中文，只返回JSON数组，每个元素是中文名，不要解释：{json.dumps(names_en, ensure_ascii=False)}"
                            resp = self._client.post(
                                f"{api_base}/chat/completions",
                                json={
                                    "model": "deepseek-chat",
                                    "messages": [
                                        {"role": "system", "content": "你是Steam游戏名翻译专家。只返回JSON数组，不要任何其他文字。"},
                                        {"role": "user", "content": prompt},
                                    ],
                                    "temperature": 0.1,
                                    "max_tokens": 1000,
                                },
                                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            )
                            resp.raise_for_status()
                            result = resp.json()
                            content = result["choices"][0]["message"]["content"].strip()
                            # Parse JSON from response
                            import re
                            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
                            if json_match:
                                translations = json.loads(json_match.group())
                                for i, d in enumerate(need_translate):
                                    if i < len(translations) and translations[i]:
                                        d.name_cn = translations[i]
                                        d._translated = True
                                        logger.info(f"  翻译: {d.name_en or d.name} → {d.name_cn}")
                        except Exception as e:
                            logger.warning(f"批量翻译失败: {e}")
                    else:
                        logger.info("无 DeepSeek API Key，跳过翻译")
            else:
                logger.debug("无英文名需要翻译")

            # 补充硬编码翻译（API 翻译经常不通，用预置表兜底）
            FALLBACK_TRANSLATIONS = {
                "Resident Evil 4": "生化危机 4",
                "Resident Evil Requiem": "恶灵附身：安魂曲",
                "Escape the Backrooms": "逃离密室",
                "Sons Of The Forest": "森林之子",
                "Grand Theft Auto V Enhanced": "Grand Theft Auto V 增强版",
                "Cuphead & The Delicious Last Course": "茶杯头：最后的美餐",
                "Street Fighter 6 Years 1-2 Fighters Edition": "街头霸王6 第1-2年斗士版",
                "Palworld": "幻兽帕鲁",
                "Forza Horizon 5": "极限竞速：地平线 5",
                "Escape the Backrooms": "逃离密室",
            }
            for d in deals:
                en = d.name_en or d.name
                cn = d.name_cn or ""
                if not cn or cn == "MISSING" or cn == en:
                    if en in FALLBACK_TRANSLATIONS:
                        d.name_cn = FALLBACK_TRANSLATIONS[en]
                        d._translated = True

            # 标记 DLC/Bundle（type=1 表示 Bundle/DLC、
            # PARENT_APPID_MAP 作为兜底）
            items = data.get("specials", {}).get("items", [])
            type_map = {item["id"]: item.get("type", 0) for item in items if "id" in item}
            for d in deals:
                if type_map.get(d.appid) == 1 or d.appid in PARENT_APPID_MAP:
                    d.is_dlc = True

            return deals
        except httpx.HTTPStatusError as e:
            logger.error(f"Steam API HTTP {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Steam API 连接失败: {e}")
            return []
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Steam API 数据解析异常: {e}")
            return []

    def _fetch_bilingual_names(self, appids: list[int]) -> dict[int, dict]:
        """并行查询 appdetails + appreviews，返回 {appid: {en, cn, review_score, review_desc}}"""
        import concurrent.futures

        REVIEW_URL = "https://store.steampowered.com/appreviews"

        def _get(appid: int) -> dict:
            info = {"en": "", "cn": "", "review_score": 0, "review_desc": "", "header_image": ""}
            try:
                url = f"{self.API_BASE}/appdetails"
                r = self._client.get(url, params={"appids": appid, "l": "schinese"})
                detail = r.json().get(str(appid), {}).get("data", {})
                info["cn"] = detail.get("name", "")
                info["header_image"] = detail.get("header_image", "")

                r = self._client.get(url, params={"appids": appid, "l": "english"})
                info["en"] = r.json().get(str(appid), {}).get("data", {}).get("name", "")

                # 同时获取好评率（appreviews API 才有准确数据）
                rr = self._client.get(
                    f"{REVIEW_URL}/{appid}",
                    params={"json": 1, "language": "english", "filter": "summary"},
                )
                qs = rr.json().get("query_summary", {})
                total = qs.get("total_reviews", 0)
                pos = qs.get("total_positive", 0)
                if total > 0:
                    info["review_score"] = round(pos / total * 100)
                    info["review_desc"] = qs.get("review_score_desc", "")

                return {appid: info}
            except Exception:
                return {appid: info}

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_get, appids))

        merged = {}
        for r in results:
            merged.update(r)
        return merged

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
