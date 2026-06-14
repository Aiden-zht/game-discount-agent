"""Rich article generator for WeChat Official Account

Generates HTML articles with:
- Steam game header images (from Steam CDN)
- Color-coded discount badges
- Review scores when available
- Clean sections
"""

import json
import logging
from datetime import datetime
from typing import Optional
import httpx

from steam_scraper import GameDeal

logger = logging.getLogger(__name__)

# Discount tiers: (min, max, emoji, hex_color, label)
DISCOUNT_TIERS = [
    (75, 100, "🔥", "#e74c3c", "特惠"),
    (50, 74, "⭐", "#e67e22", "超值"),
    (25, 49, "👍", "#f1c40f", "推荐"),
    (0, 24, "💫", "#95a5a6", "一般"),
]


def _discount_tag(d: GameDeal) -> tuple:
    """Return (emoji, hex_color, label) for the discount level."""
    for lo, hi, emoji, color, label in DISCOUNT_TIERS:
        if lo <= d.discount_percent <= hi:
            return emoji, color, label
    return "💫", "#95a5a6", ""


def _game_card(d: GameDeal, rank: int = 0, image_map: dict = None) -> str:
    """Generate HTML card for a single game deal."""
    if image_map is None:
        image_map = {}
    emoji, color, label = _discount_tag(d)

    # 折扣标签固定宽度，确保三个区域一致
    badge = f'<span style="display:inline-block;background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-weight:bold;font-size:12px;min-width:72px;text-align:center;margin-right:8px">{emoji} -{d.discount_percent}%</span>'

    # 序号圆标
    rank_badge = f'<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;background:{color};color:#fff;border-radius:50%;font-size:11px;font-weight:bold;margin-right:6px">{rank}</span>' if rank else ''

    # 价格醒目放大
    price = f'<span style="font-weight:bold;font-size:17px;color:{color}">{d.final_price}</span>'
    if d.original_price_cents > 0:
        price += f' <span style="font-size:12px;color:#999;text-decoration:line-through;margin-left:6px">{d.original_price}</span>'

    # 游戏名显示格式：
    # - Palworld / 幻兽帕鲁 (Steam 原生双语)     → 保持原样
    # - Resident Evil 4 / 生化危机4 (API 有中文名) → en / cn
    # - Escape the Backrooms [逃离密室] (翻译的)    → en [cn]
    # - Cuphead & The Delicious Last Course          → 仅英文
    # ⚠️ R.E.P.O. 等无官方中文名的游戏：name_cn=name_en，过滤后不会进入列表
    en_name = d.name_en or d.name
    cn_name = d.name_cn or d.name
    if cn_name and " / " in cn_name:
        # Already bilingual from Steam (e.g. "Palworld / 幻兽帕鲁")
        display_name = cn_name
    elif getattr(d, "_translated", False) and cn_name and cn_name != en_name:
        # Translated: same / format
        display_name = f"{en_name} / {cn_name}"
    elif en_name and cn_name and en_name != cn_name:
        # Has both names and they differ — check for duplicate English in cn_name
        # e.g. "DAVE THE DIVER / 潜水员戴夫 DAVE THE DIVER" → "DAVE THE DIVER / 潜水员戴夫"
        if en_name.lower() in cn_name.lower():
            # cn_name contains the English name — strip it and use only Chinese part
            cn_clean = cn_name.replace(en_name, "").strip().strip("/").strip()
            if cn_clean:
                display_name = f"{en_name} / {cn_clean}"
            else:
                # Nothing left after stripping English — use English only
                display_name = en_name
                logger.warning(f"游戏名重复清理后为空: {d.name} (appid {d.appid}), 使用英文名")
        else:
            display_name = f"{en_name} / {cn_name}"
    else:
        # name_cn == name_en or both empty — no Chinese name available
        # Per spec B25: allowed for games without official Chinese name (R.E.P.O. etc.)
        display_name = en_name or d.name
        logger.info(f"游戏 {d.appid} 无中文名，显示纯英文: {display_name}")

    # DLC/Bundle 标注
    dlc_tag = ' <span style="font-size:11px;color:#e67e22;font-weight:normal;background:#fef3e2;padding:1px 5px;border-radius:3px">DLC</span>' if d.is_dlc else ''
    display_name = f"{display_name}{dlc_tag}"

    # Review score (from appreviews API)
    review = ""
    if d.review_score > 0:
        color = "#27ae60" if d.review_score >= 80 else "#e67e22" if d.review_score >= 60 else "#e74c3c"
        review = f'<div style="font-size:11px;color:{color};margin-top:4px">👍 {d.review_score}% 好评</div>'

    # Game header image - use WeChat CDN URL only
    # ⚠️ No fallback to Steam URL (spec 4.3 + B11: Steam CDN blocks on WeChat)
    # Games without WeChat CDN image are filtered out in Phase 1 (cron_digest.py)
    img_url = image_map.get(d.appid, "")
    if not img_url:
        logger.warning(f"No WeChat CDN image for {d.name} (appid {d.appid}) — should have been filtered in Phase 1")
        img = ""  # skip image, don't use Steam URL
    else:
        img = f'<img src="{img_url}" style="width:100%;max-width:460px;border-radius:6px;margin:8px 0 0 0" loading="lazy"/>'

    return f'''<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:12px;margin:8px 0 2px 0">
<div style="display:flex;justify-content:space-between;align-items:center">
<div>
<div style="margin-bottom:4px">{rank_badge}{badge} <span style="font-weight:bold;font-size:15px">{display_name}</span></div>
<div>{price}</div>
{review}
</div>
</div>
{img}
</div>'''


class ArticleGenerator:
    """WeChat Official Account article generator"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""
        self._client: Optional[httpx.Client] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._client:
            self._client.close()

    def generate_daily_digest(
        self, steam_deals: list[GameDeal], epic_free: list[GameDeal],
        image_map: dict = None,
        version_id: str = "",
        deadline: str = ""
    ) -> str:
        """Generate a rich WeChat article from deal data.
        image_map: {appid: wechat_cdn_url} for game images uploaded to WeChat.
        version_id: short version tag (e.g. "V260610-a3f8c2"), added to article footer.
        deadline: 优惠截止日期（如 "2026年06月26日"），用于限时标注。
        """
        if image_map is None:
            image_map = {}
        today_cn = datetime.now().strftime("%Y年%m月%d日")

        # Dedup by appid
        seen = set()
        unique = []
        for d in sorted(steam_deals, key=lambda x: x.discount_percent, reverse=True):
            if d.appid not in seen:
                seen.add(d.appid)
                unique.append(d)

        # Sort by heat score: discount * review * IP_weight (per spec: 按热度排序，不设上限)
        def _heat_score(d):
            dim1 = d.discount_percent * d.review_score / 100.0
            ip = 1.8 if d.original_price_cents >= 29800 else 1.4 if d.original_price_cents >= 15800 else 1.0
            return dim1 * ip

        unique.sort(key=_heat_score, reverse=True)

        if not unique and not epic_free:
            ver_footer = f'<p style="font-size:10px;color:#ccc;text-align:right">Version: V{version_id}</p>' if version_id else ''
            return f'''<h2>📭 暂无折扣数据</h2>
<p>{today_cn}，Steam 数据暂时不可达。</p>
<blockquote>建议直接访问 Steam 查看最新特惠</blockquote>
{ver_footer}'''

        parts = []

        # Header
        parts.append('<h2>🎮 Steam 今日特惠</h2>')
        parts.append(f'<p style="color:#666;font-size:13px">{today_cn} · 共 {len(unique)} 款值得推荐 · 按综合热度排序</p>')
        if deadline:
            parts.append(f'<p style="color:#e74c3c;font-size:14px;font-weight:bold">⏰ 优惠截止时间：{deadline}</p>')
        else:
            parts.append('<p style="color:#e74c3c;font-size:14px;font-weight:bold">⏰ 限时领取，过期不候！</p>')
        parts.append('<hr style="border:none;border-top:2px solid #eee;margin:12px 0"/>')

        # 区分游戏和 DLC
        games = [d for d in unique if not d.is_dlc]
        dlcs = [d for d in unique if d.is_dlc]

        # ---- 游戏专区 ----
        # 主卡区固定 9 款卡片，不足 9 款时从 DLC/低折扣补卡，超过 9 款时多余的走低列表
        MAIN_MAX = 9

        # 按热度分档，每档内按折扣×好评率排序
        tier1 = [d for d in games if d.discount_percent >= 75]
        tier2 = [d for d in games if 50 <= d.discount_percent < 75]
        tier3 = [d for d in games if d.discount_percent < 50]
        tier1.sort(key=lambda d: d.discount_percent * d.review_score, reverse=True)
        tier2.sort(key=lambda d: d.discount_percent * d.review_score, reverse=True)
        tier3.sort(key=lambda d: d.discount_percent * d.review_score, reverse=True)

        # 全量有序游戏列表
        all_games_sorted = tier1 + tier2 + tier3
        total_games = len(all_games_sorted)

        # 主卡区取前 MAIN_MAX 款
        main_show = all_games_sorted[:MAIN_MAX]
        overflow_games = all_games_sorted[MAIN_MAX:] if total_games > MAIN_MAX else []
        main_appids = set(d.appid for d in main_show)

        # 拆分各档的展示/溢出
        def _split(tier):
            show = [d for d in tier if d.appid in main_appids]
            over = [d for d in tier if d.appid not in main_appids]
            return show, over

        tier1_main, tier1_overflow = _split(tier1)
        tier2_main, tier2_overflow = _split(tier2)
        tier3_main, tier3_overflow = _split(tier3)

        # ---- 史低 (≥75%) — 游戏 ----
        if tier1_main:
            parts.append('<h3 style="color:#e74c3c;margin:16px 0 8px 0;padding-bottom:10px;border-bottom:3px solid #e74c3c">🔥 特惠专区 · 游戏</h3>')
            parts.append('<p style="font-size:12px;color:#999;margin:0 0 8px 0">限时折扣 75% 以上</p>')
            for i, d in enumerate(tier1_main, 1):
                parts.append(_game_card(d, rank=i, image_map=image_map))

        # ---- 超值 (50-74%) — 游戏 ----
        if tier2_main:
            parts.append('<h3 style="color:#e67e22;margin:32px 0 8px 0;padding-bottom:10px;border-bottom:3px solid #e67e22">⭐ 超值推荐 · 游戏</h3>')
            parts.append('<p style="font-size:12px;color:#999;margin:0 0 8px 0">折扣 50% 以上，值得入手</p>')
            for i, d in enumerate(tier2_main, 1):
                parts.append(_game_card(d, rank=i, image_map=image_map))

        # ---- 其他 (<50%) — 游戏 ----
        if tier3_main:
            parts.append('<h3 style="color:#95a5a6;margin:32px 0 8px 0;padding-bottom:10px;border-bottom:3px solid #95a5a6">💫 更多折扣 · 游戏</h3>')
            for i, d in enumerate(tier3_main, 1):
                parts.append(_game_card(d, rank=i, image_map=image_map))

        # ---- 更多推荐（纯文字列表，无配图） ----
        overflow_all = overflow_games + dlcs
        # 去重保持顺序
        seen_overflow = set()
        overflow_unique = []
        for d in overflow_all:
            if d.appid not in seen_overflow:
                seen_overflow.add(d.appid)
                overflow_unique.append(d)
        if overflow_unique:
            parts.append('<hr style="border:none;border-top:1px solid #eee;margin:24px 0"/>')
            parts.append('<h3 style="color:#666;margin:20px 0 10px 0;font-size:16px">📋 更多推荐</h3>')
            parts.append(f'<p style="font-size:12px;color:#999;margin:0 0 10px 0">共 {total_games} 款游戏符合推荐标准，以下为其余 {len(overflow_unique)} 款（含 DLC）</p>')
            for d in overflow_unique:
                emoji, color, label = _discount_tag(d)
                dlc_tag = ' [DLC]' if d.is_dlc else ''
                display_en = d.name_en or d.name
                display_cn = (d.name_cn or "").replace(display_en, "").strip().strip("/").strip()
                if display_cn and display_en and display_en != display_cn:
                    name_line = f'{display_en} / {display_cn}'
                elif display_cn:
                    name_line = display_cn
                else:
                    name_line = display_en
                if dlc_tag:
                    name_line += dlc_tag
                original = d.original_price if d.original_price != "¥ 0.00" else ""
                price_parts = [f'<span style="color:{color};font-weight:bold">{d.final_price}</span>']
                if original:
                    strike = " <span style='color:#999;text-decoration:line-through;font-size:11px'>" + original + "</span>"
                    price_parts.append(strike)
                price_parts.append(f' <span style="color:{color};font-size:11px">{emoji} -{d.discount_percent}%</span>')
                parts.append(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px dashed #eee;font-size:13px">'
                    f'<span style="color:#333">{name_line}</span>'
                    f'<span>{" ".join(price_parts)}</span>'
                    f'</div>'
                )

        # DLC 已合并到"更多推荐"纯文字列表

        # Epic free section
        if epic_free:
            parts.append('<h3 style="color:#e74c3c">🎁 Epic 本周免费</h3>')
            for d in epic_free:
                parts.append(f'''<div style="background:#f0faf0;border:1px solid #c8e6c9;border-radius:10px;padding:12px;margin:12px 0;text-align:center">
<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:3px;font-weight:bold;font-size:12px">🆓 免费</span>
<div style="font-weight:bold;font-size:15px;margin:8px 0">{d.name}</div>
<img src="{d.header_image}" style="width:100%;border-radius:6px"/>
<div style="color:#e74c3c;font-size:13px;margin-top:8px">⏰ 限时领取，过期不候！</div>
</div>''')

        # Footer
        parts.extend([
            '<hr style="border:none;border-top:1px solid #eee;margin:16px 0"/>',
            '<blockquote style="font-size:12px;color:#999">📊 数据来源：Steam Store API · 每日 10:00 自动更新<br/>📱 关注本号，每日推送最值得买的游戏折扣</blockquote>',
        ])

        # Version ID — visible footer so we can tell which session/agent published which version
        parts.append(
            '<p style="font-size:10px;color:#ccc;text-align:right;padding-top:8px">Version: V' + version_id + '</p>'
        )

        return "\n".join(parts)

    def generate_free_game_alert(self, epic_free: list[GameDeal]) -> str:
        """Generate Epic free games alert."""
        if not epic_free:
            return ""
        parts = [
            '<h2>🎉 Epic 本周免费</h2>',
            '<p style="color:#e74c3c">🆓 限时免费领取，错过不再！</p>',
        ]
        for d in epic_free:
            parts.append(f'''<div style="background:#f0faf0;border:1px solid #c8e6c9;border-radius:10px;padding:12px;margin:12px 0">
<div style="font-weight:bold;font-size:15px">{d.name}</div>
<img src="{d.header_image}" style="width:100%;border-radius:6px"/>
<div style="color:#e74c3c;font-size:12px;margin-top:8px">⏰ 本周限免</div>
</div>''')
        return "\n".join(parts)



def main():
    logging.basicConfig(level=logging.INFO)
    from steam_scraper import SteamScraper
    with SteamScraper(timeout=30) as s:
        deals = s.get_deals()
    gen = ArticleGenerator()
    article = gen.generate_daily_digest(deals, [])
    print(article)

if __name__ == "__main__":
    main()