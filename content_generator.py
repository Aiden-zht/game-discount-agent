"""
AI 内容生成器

调用 DeepSeek API 根据游戏折扣数据生成公众号文章。
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional
import httpx

from steam_scraper import GameDeal

logger = logging.getLogger(__name__)


# 从环境变量读取 API key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


class ArticleGenerator:
    """AI 公众号文章生成器"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self._client: Optional[httpx.Client] = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self._client:
            self._client.close()

    def _get_client(self) -> httpx.Client:
        """懒初始化 HTTP 客户端（没 key 时无需创建）"""
        if self._client is None:
            self._client = httpx.Client(
                timeout=60,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
        return self._client

    def generate_daily_digest(
        self, steam_deals: list[GameDeal], epic_free: list[GameDeal]
    ) -> str:
        """生成每日折扣简报文章"""
        today = datetime.now().strftime("%Y年%m月%d日")

        # 按折扣排序，取前20
        sorted_deals = sorted(steam_deals, key=lambda d: d.discount_percent, reverse=True)[:20]

        if not sorted_deals and not epic_free:
            return self._empty_digest(today)

        # 构建数据
        deals_text = "\n".join(
            f"{i+1}. 【-{d.discount_percent}%】{d.name} — 原价{d.original_price}，现价{d.final_price}"
            for i, d in enumerate(sorted_deals[:15])
        )

        free_text = "\n".join(
            f"{i+1}. {d.name}（免费领！）"
            for i, d in enumerate(epic_free)
        ) or "暂无"

        system_prompt = """你是一个游戏折扣公众号的主编。你的文章风格：
- 口语化、接地气、带一点幽默
- 开头写一段引语，聊聊当天游戏圈的小热点
- 每个游戏用1-2句话推荐，突出折扣力度和值得买的理由
- 结尾加一句互动引导
- 不用markdown，用纯文字
- 全文400-600字"""

        user_prompt = f"""今天是{today}。请写一篇「今日Steam折扣简报」公众号文章。

Steam今日特惠（按折扣排序）：
{deals_text}

Epic免费游戏：
{free_text}

要求：口语化公众号风格，第一段引语写一下最近的热门游戏话题，重点推荐折扣>50%的游戏。"""

        if not self.api_key:
            return self._template_digest(today, sorted_deals, epic_free)

        try:
            resp = self._get_client().post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except Exception as e:
            logger.error(f"AI 生成失败: {e}")
            return self._template_digest(today, sorted_deals, epic_free)

    def generate_free_game_alert(self, epic_free: list[GameDeal]) -> str:
        """生成限免/免费游戏提醒"""
        today = datetime.now().strftime("%Y年%m月%d日")

        if not epic_free:
            return ""

        free_list = "\n".join(
            f"🎮 {d.name}" for d in epic_free
        )

        system_prompt = """你是一个游戏福利提醒公众号。风格：激动、紧迫感、简短有力。"""
        user_prompt = f"""写一篇「本周Epic免费游戏」提醒短文，300字左右。

本周免费：
{free_list}

要求：强调免费、限时领取、截止日期，语气有紧迫感。"""

        if not self.api_key:
            return f"""🎉 本周Epic免费游戏

{free_list}

⏰ 限时免费，错过不再！快去领取。

—— 游戏好价Agent"""

        try:
            resp = self._get_client().post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 800,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"AI 生成免费提醒失败: {e}")
            return f"🎉 本周Epic免费游戏\n\n{free_list}\n\n⏰ 限时免费，快去领取！"

    def _empty_digest(self, today: str) -> str:
        return f"""📭 今日({today})暂无游戏折扣数据

可能是 Steam API 暂时不可达，数据将在下次更新时恢复。

💡 建议直接访问 Steam 查看最新特惠。

—— 游戏好价Agent"""

    def _template_digest(
        self, today: str, deals: list[GameDeal], epic_free: list[GameDeal]
    ) -> str:
        """无 API Key 时使用模板生成"""
        lines = [f"📢 今日Steam折扣简报 | {today}", ""]

        if deals:
            lines.append("🔥 热门特惠：")
            for d in deals[:12]:
                tag = "🔥" if d.discount_percent >= 50 else "💫"
                lines.append(f"  {tag} 【-{d.discount_percent}%】{d.name}")
                lines.append(f"     原价{d.original_price} → 现价{d.final_price}")
            lines.append("")

        if epic_free:
            lines.append("🎁 Epic 本周免费：")
            for d in epic_free:
                lines.append(f"  🆓 {d.name}")
            lines.append("")

        lines.append("💡 数据来源: Steam / Epic API")
        lines.append("—— 游戏好价Agent，每日自动更新")

        return "\n".join(lines)


def main():
    """测试"""
    logging.basicConfig(level=logging.INFO)

    # 测试模板模式
    from steam_scraper import SteamScraper

    with SteamScraper() as s:
        deals = s.get_deals()

    gen = ArticleGenerator(api_key="")  # 无 key 时用模板
    article = gen.generate_daily_digest(deals, [])
    print(article)
    print("\n" + "=" * 40)
    print(f"\n文章长度: {len(article)} 字")


if __name__ == "__main__":
    main()
