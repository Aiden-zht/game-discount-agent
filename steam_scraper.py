"""
Steam 折扣/特惠爬虫

抓取 Steam 当前特惠游戏列表，包括折扣率、价格、好评率等信息。
使用 Steam Store API（官方接口，无需 token）。

翻译流程（3层降级）：
1. Steam API appdetails?l=schinese 返回中文名 → 权威源
2. FALLBACK 硬编码表 → 兜底
3. LLM 批量翻译 → 仅当结果包含中文字符时才覆盖

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
    deadline: str = ""  # 优惠截止时间 (如 "2026-06-26")

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

    def __init__(self, timeout: int = 15, proxy: str = "socks5://127.0.0.1:7891"):
        self._client = httpx.Client(
            timeout=timeout,
            proxy=proxy,
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

    def _format_deadline(self, discount_expiration) -> str:
        """将 Steam discount_expiration 时间戳转为北京时间日期。"""
        try:
            from datetime import datetime, timezone, timedelta
            if not discount_expiration:
                return ""
            ts = int(discount_expiration)
            dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            cst = timezone(timedelta(hours=8))
            dt_cst = dt_utc.astimezone(cst)
            return dt_cst.strftime("%Y年%m月%d日")
        except Exception as e:
            logger.warning(f"计算截止日期失败: {e}")
        return ""

    def _compute_deadline(self, data: dict) -> str:
        """从 specials 的 discount_expiration 计算最早截止时间（北京时间）。

        仅用于兜底/摘要，不再注入给所有游戏；每款游戏以自身 item 的
        discount_expiration 为准。
        """
        items = data.get("specials", {}).get("items", [])
        expirations = [int(item["discount_expiration"]) for item in items if item.get("discount_expiration")]
        return self._format_deadline(min(expirations)) if expirations else ""

    def get_deals(self) -> list[GameDeal]:
        """获取 Steam 当前特惠游戏（带英文+中文双语名）

        翻译流程（3层降级，按顺序执行）：
        1. Steam API appdetails?l=schinese 返回中文名 → 权威源
        2. FALLBACK 硬编码表 → 兜底
        3. LLM 批量翻译 → 仅当翻译结果包含中文字符时才覆盖

        去重后最多从 top_sellers 补充至 9 款。
        """
        # 硬编码 fallback 表：英文原名 → 中文官方名
        FALLBACK = {
            "MECCHA CHAMELEON": "机械变色龙",
            "Resident Evil 4": "生化危机4",
            "DAVE THE DIVER": "潜水员戴夫",
            "Forza Horizon 5": "极限竞速：地平线 5",
            "Voidling Bound": "沃德灵：共生",
            "R.E.P.O.": "R.E.P.O.",
            "Road to Empress II": "女王的游戏：盛世天下 女帝篇",
        }

        try:
            data = self._fetch_featured()
            items = data.get("specials", {}).get("items", [])
            deals = [self._api_item_to_deal(item) for item in items]

            # 计算本批最早截止日期，仅给缺失 item deadline 的补充数据兜底
            earliest_deadline = self._compute_deadline(data)

            # 去重（Steam API 可能有重复条目）
            seen_ids = set()
            unique_deals = []
            for d in deals:
                if d.appid and d.appid not in seen_ids:
                    seen_ids.add(d.appid)
                    unique_deals.append(d)
            deals = unique_deals

            # 批量查询 appdetails + appreviews 获取双语名和好评率
            appids = [d.appid for d in deals if d.appid]
            bilingual = self._fetch_bilingual_names(appids) if appids else {}

            for d in deals:
                if d.appid not in bilingual:
                    continue
                info = bilingual[d.appid]
                d.name_en = info["en"]
                d.name_cn = info["cn"]
                if info["header_image"]:
                    d.header_image = info["header_image"]
                if info["review_score"] > 0:
                    d.review_score = info["review_score"]
                    d.review_desc = info["review_desc"]

                # 清理 Steam API l=schinese 返回的英文副标题混入
                en_raw = (d.name_en or "").strip()
                cn_raw = (d.name_cn or "").strip()
                if en_raw and cn_raw and en_raw.lower() in cn_raw.lower():
                    cn_clean = cn_raw.replace(en_raw, "").strip().strip("/").strip()
                    if cn_clean:
                        d.name_cn = cn_clean

            # 第2层：FALLBACK 表兜底
            for d in deals:
                en = (d.name_en or d.name).strip()
                cn = (d.name_cn or "").strip()
                if en and (not cn or cn == en):
                    fallback_cn = FALLBACK.get(en)
                    if fallback_cn:
                        d.name_cn = fallback_cn
                        logger.info(f"FALLBACK: {en} → {fallback_cn}")

            # 第3层：LLM 批量翻译（仅翻译中文名空缺或中英文相同的情况）
            need_translate = []
            for d in deals:
                en = (d.name_en or d.name).strip()
                cn = (d.name_cn or "").strip()
                if en and (not cn or cn == en or cn == "MISSING"):
                    need_translate.append(d)

            if need_translate:
                self._batch_translate(need_translate)

            # 标记 DLC/Bundle
            type_map = {item["id"]: item.get("type", 0) for item in items if "id" in item}
            for d in deals:
                if type_map.get(d.appid) == 1 or d.appid in PARENT_APPID_MAP:
                    d.is_dlc = True

            # 不足9款时从 top_sellers 补充
            self._supplement_top_sellers(data, deals, seen_ids, FALLBACK, need_translate, earliest_deadline)

            if need_translate:
                self._batch_translate(need_translate)

            return deals
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch featured games: {e.response.status_code}")
            return []
        except httpx.TimeoutException:
            logger.error("Timeout fetching featured games")
            return []

    def _supplement_top_sellers(self, data: dict, deals: list[GameDeal],
                                seen_ids: set, fallback: dict,
                                need_translate: list,
                                deadline: str = "") -> None:
        """从 top_sellers 补充不足9款的游戏"""
        min_games = 9
        if len(deals) >= min_games:
            return

        top_sellers_items = data.get("top_sellers", {}).get("items", [])
        for ts_item in top_sellers_items:
            ts_appid = ts_item.get("id")
            if not ts_appid or ts_appid in seen_ids:
                continue

            # 优先用 discount_percent，或 final_price < regular_price 判断有折扣
            discount_pct = ts_item.get("discount_percent", 0)
            final_price = ts_item.get("final_price", 0)
            regular_price = ts_item.get("regular_price", 0)
            if discount_pct and discount_pct > 0:
                pass  # 正常有折扣
            elif final_price > 0 and regular_price > 0 and final_price < regular_price:
                discount_pct = round((1 - final_price / regular_price) * 100)
            if not discount_pct or discount_pct <= 0:
                continue

            ts_deal = self._api_item_to_deal(ts_item)

            # 查询 appdetails + appreviews 获取数据
            ts_bilingual = self._fetch_bilingual_names([ts_appid])
            if ts_appid not in ts_bilingual:
                continue
            info = ts_bilingual[ts_appid]
            ts_deal.name_en = info["en"]
            ts_deal.name_cn = info["cn"]
            if info["header_image"]:
                ts_deal.header_image = info["header_image"]
            if info["review_score"] > 0:
                ts_deal.review_score = info["review_score"]
                ts_deal.review_desc = info["review_desc"]
            else:
                # 无评价数据的游戏不补充
                logger.info(f"跳过 top_sellers 补充（无评价数据）: {ts_item.get('name', '')}")
                continue

            # 清理英文副标题混入
            en_raw = (ts_deal.name_en or "").strip()
            cn_raw = (ts_deal.name_cn or "").strip()
            if en_raw and cn_raw and en_raw.lower() in cn_raw.lower():
                cn_clean = cn_raw.replace(en_raw, "").strip().strip("/").strip()
                if cn_clean:
                    ts_deal.name_cn = cn_clean

            # 从 appdetails 获取准确折扣（带 cc=CN 强制返回 CNY 价格）
            try:
                detail_url = f"{self.API_BASE}/appdetails"
                detail_resp = self._client.get(detail_url, params={"appids": ts_appid, "l": "schinese", "cc": "CN"})
                detail = detail_resp.json().get(str(ts_appid), {}).get("data", {})
                if detail:
                    dp = detail.get("discount_percent", 0)
                    if dp and dp > 0:
                        ts_deal.discount_percent = dp
                    pov = detail.get("price_overview", {})
                    fp = pov.get("final", 0)
                    if fp and pov.get("currency") == "CNY":
                        # CNY 最小单位=分，直接用
                        ts_deal.final_price_cents = fp
            except Exception:
                pass

            # 对补充的游戏也执行 FALLBACK
            en_f = (ts_deal.name_en or ts_deal.name).strip()
            cn_f = (ts_deal.name_cn or "").strip()
            if en_f and (not cn_f or cn_f == en_f):
                fb = fallback.get(en_f)
                if fb:
                    ts_deal.name_cn = fb
            if en_f and (not cn_f or cn_f == en_f or cn_f == "MISSING"):
                need_translate.append(ts_deal)

            ts_deal.source = "top_sellers_supplement"
            deals.append(ts_deal)
            if not ts_deal.deadline:
                ts_deal.deadline = deadline  # 仅缺失 discount_expiration 时使用本批最早截止日期兜底
            seen_ids.add(ts_appid)
            logger.info(f"从 top_sellers 补充: {ts_deal.name} (appid={ts_appid}, -{ts_deal.discount_percent}%, 好评{ts_deal.review_score}%)")
            if len(deals) >= min_games:
                break

    def _batch_translate(self, deals: list[GameDeal]) -> None:
        """LLM 批量翻译游戏名。

        仅当翻译结果**不是英文**（包含中文字符）时才覆盖 name_cn。
        翻译 API 返回英文原名视为失败，保留 Steam API 的原始数据。
        """
        # 过滤掉 FALLBACK 已覆盖的游戏
        to_translate = []
        for d in deals:
            cn = (d.name_cn or "").strip()
            if not cn or cn == d.name_en:
                to_translate.append(d)
        if not to_translate:
            return

        # 读 API Key
        dotenv_path = os.path.expanduser("~/.hermes/.env")
        api_key = ""
        if os.path.isfile(dotenv_path):
            with open(dotenv_path) as f:
                for line in f:
                    line = line.strip()
                    if "IFLYTEK_SPARK_API_KEY" in line and "***" not in line:
                        api_key = line.split("=", 1)[1].strip()
                        break
        if not api_key:
            api_key = os.environ.get("IFLYTEK_SPARK_API_KEY", "")
        if not api_key:
            logger.warning("No API key found, skipping translation")
            return

        en_names = [d.name_en or d.name for d in to_translate]
        import re
        try:
            resp = self._client.post(
                "https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions",
                json={
                    "model": "xopqwen36v35b",
                    "messages": [
                        {"role": "system", "content": "你是Steam游戏名翻译专家。只返回JSON数组，每个元素是简体中文游戏名。如果游戏名是品牌名/缩写且没有官方中文名，请返回英文原名。不要添加任何解释或其他文字。"},
                        {"role": "user", "content": f"翻译以下游戏名：{json.dumps(en_names, ensure_ascii=False)}"},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"].strip()
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                translations = json.loads(json_match.group())
                for i, d in enumerate(to_translate):
                    if i < len(translations) and translations[i]:
                        translated_cn = translations[i].strip()
                        # 只覆盖：翻译结果与原名不同，且包含中文字符
                        has_cn = any('\u4e00' <= c <= '\u9fff' for c in translated_cn)
                        if has_cn and translated_cn != d.name_en:
                            old_cn = d.name_cn or "(empty)"
                            d.name_cn = translated_cn
                            logger.info(f"  翻译: {d.name_en} → {translated_cn} (原: {old_cn})")
                        else:
                            logger.info(f"  翻译跳过(非中文): {d.name_en}")
            else:
                logger.warning(f"翻译返回格式异常: {content[:200]}")
        except Exception as e:
            logger.warning(f"翻译失败: {e}")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _fetch_bilingual_names(self, appids: list[int]) -> dict[int, dict]:
        """并行查询 appdetails + appreviews，返回 {appid: {en, cn, review_score, review_desc}}"""
        import concurrent.futures

        REVIEW_URL = "https://store.steampowered.com/appreviews"

        def _get(appid: int) -> dict:
            info = {"en": "", "cn": "", "review_score": 0, "review_desc": "", "header_image": ""}
            try:
                # 中文名+价格信息（schinese + cc=CN 强制返回 CNY 价格）
                url = f"{self.API_BASE}/appdetails"
                r = self._client.get(url, params={"appids": appid, "l": "schinese", "cc": "CN"})
                detail = r.json().get(str(appid), {}).get("data", {})
                info["cn"] = detail.get("name", "")
                info["header_image"] = detail.get("header_image", "")
                if not info["header_image"]:
                    info["header_image"] = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"

                # 英文名（english）
                r = self._client.get(url, params={"appids": appid, "l": "english"})
                info["en"] = r.json().get(str(appid), {}).get("data", {}).get("name", "")

                # 好评率（appreviews API 才有准确数据）
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
            except Exception as e:
                logger.warning(f"获取双语名+好评率失败 (appid {appid}): {e}")
                return {appid: info}

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_get, appids))

        merged = {}
        for r in results:
            merged.update(r)
        return merged

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
            deadline=self._format_deadline(item.get("discount_expiration")),
        )

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
