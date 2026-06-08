"""Rich article generator for WeChat Official Account

Generates HTML articles with:
- Steam game header images (from Steam CDN)
- Color-coded discount badges
- Review scores when available
- Clean sections
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional
import httpx

from steam_scraper import GameDeal

logger = logging.getLogger(__name__)

# Discount tiers: (min, max, emoji, hex_color, label)
DISCOUNT_TIERS = [
    (75, 100, "🔥", "#e74c3c", "史低"),
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

    rank_badge = f'<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;background:{color};color:#fff;border-radius:50%;font-size:11px;font-weight:bold;margin-right:6px">{rank}</span>' if rank else ''

    badge = f'<span style="background:{color};color:#fff;padding:2px 6px;border-radius:3px;font-weight:bold;font-size:12px">{emoji} -{d.discount_percent}%</span>'

    price = f'<span style="font-weight:bold;font-size:15px;color:{color}">{d.final_price}</span>'
    if d.original_price_cents > 0:
        price += f' <span style="font-size:12px;color:#999;text-decoration:line-through">{d.original_price}</span>'

    # 双语名: "English / 简体中文"
    en_name = d.name_en or d.name
    cn_name = d.name_cn or d.name
    if en_name and cn_name and en_name != cn_name:
        display_name = f"{en_name} / {cn_name}"
    else:
        display_name = en_name or d.name

    # Review score (from appreviews API)
    review = ""
    if d.review_score > 0:
        color = "#27ae60" if d.review_score >= 80 else "#e67e22" if d.review_score >= 60 else "#e74c3c"
        review = f'<div style="font-size:12px;color:{color};margin-top:4px">👍 {d.review_score}% 好评 · {d.review_desc}</div>'

    # Game header image - use WeChat CDN URL if available
    img_url = image_map.get(d.appid, f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{d.appid}/header.jpg")
    img = f'<img src="{img_url}" style="width:100%;max-width:460px;border-radius:6px;margin:8px 0 0 0"/>'

    return f'''<div style="background:#fff;border:1px solid #eee;border-radius:10px;padding:12px;margin:12px 0">
<div style="display:flex;justify-content:space-between;align-items:center">
<div>
<div style="margin-bottom:4px">{rank_badge}{badge} <span style="font-weight:bold;font-size:14px">{display_name}</span></div>
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
        image_map: dict = None
    ) -> str:
        """Generate a rich WeChat article from deal data.
        image_map: {appid: wechat_cdn_url} for game images uploaded to WeChat.
        """
        if image_map is None:
            image_map = {}
        today_cn = datetime.now().strftime("%Y年%m月%d日")

        # Dedup by appid, sort by discount descending
        seen = set()
        unique = []
        for d in sorted(steam_deals, key=lambda x: x.discount_percent, reverse=True):
            if d.appid not in seen:
                seen.add(d.appid)
                unique.append(d)

        if not unique and not epic_free:
            return f'''<h2>📭 暂无折扣数据</h2>
<p>{today_cn}，Steam 数据暂时不可达。</p>
<blockquote>建议直接访问 Steam 查看最新特惠</blockquote>'''

        parts = []

        # Header
        parts.append(f'<h2>🎮 Steam 今日特惠</h2>')
        parts.append(f'<p style="color:#666;font-size:13px">{today_cn} · 共 {len(unique)} 款折扣</p>')
        parts.append('<hr style="border:none;border-top:1px solid #eee;margin:12px 0"/>')

        # Section: 史低专区 (≥75%)
        tier1 = [d for d in unique if d.discount_percent >= 75]
        if tier1:
            parts.append('<h3 style="color:#e74c3c">🔥 史低专区</h3>')
            parts.append('<p style="font-size:12px;color:#999">折扣 75% 以上，历史最低价</p>')
            for i, d in enumerate(tier1, 1):
                parts.append(_game_card(d, rank=i, image_map=image_map))

        # Section: 超值专区 (50-74%)
        tier2 = [d for d in unique if 50 <= d.discount_percent < 75]
        if tier2:
            parts.append('<h3>⭐ 超值推荐</h3>')
            parts.append('<p style="font-size:12px;color:#999">折扣 50% 以上，值得入手</p>')
            for i, d in enumerate(tier2, 1):
                parts.append(_game_card(d, rank=i, image_map=image_map))

        # Section: 其他折扣 (<50%)
        tier3 = [d for d in unique if d.discount_percent < 50]
        if tier3:
            parts.append('<h3>💫 更多折扣</h3>')
            for i, d in enumerate(tier3, 1):
                parts.append(_game_card(d, rank=i, image_map=image_map))

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