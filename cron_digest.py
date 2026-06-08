"""
每日游戏折扣公众号内容生成入口

由 Hermes cron 定时调用，串联全流程：
1. 爬取 Steam 特惠 + 热销
2. 爬取 Epic 免费游戏
3. AI/模板生成公众号文章
4. 保存到 output/ 目录
5. 返回结果给 cron 推送
"""

import logging
import os
import sys
from datetime import datetime

# 确保可以找到同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from steam_scraper import SteamScraper
from epic_scraper import EpicScraper
from content_generator import ArticleGenerator
from wechat_publisher import publish_article, Article as WeChatArticle, WeChatError, get_access_token

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def run_daily_digest() -> str:
    """执行每日折扣简报全流程，返回文章内容"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    # ---- Step 1 + 2: 共享一个 Scraper 实例获取 Steam 数据 ----
    steam_deals = []
    steam_top = []
    try:
        with SteamScraper(timeout=25) as s:
            steam_deals = s.get_deals()
            steam_top = s.get_top_sellers()
        logger.info(f"Steam 特惠: {len(steam_deals)} 个, 热销: {len(steam_top)} 个")
    except Exception as e:
        logger.error(f"Steam 爬取失败: {e}")

    # ---- Step 3: Epic 免费 ----
    epic_free = []
    try:
        with EpicScraper() as e:
            epic_free = e.get_free_games()
        logger.info(f"Epic 免费: {len(epic_free)} 个")
    except Exception as e:
        logger.error(f"Epic 爬取失败: {e}")

    # ---- Step 4: 生成文章 ----
    gen = ArticleGenerator()
    article = gen.generate_daily_digest(steam_deals, epic_free)

    # 如果有 Epic 免费，额外生成提醒
    free_alert = ""
    if epic_free:
        free_alert = gen.generate_free_game_alert(epic_free)

    # ---- Step 5: 保存到文件 ----
    digest_path = os.path.join(OUTPUT_DIR, f"digest_{today}.md")
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(article)
    logger.info(f"文章已保存: {digest_path}")

    if free_alert:
        alert_path = os.path.join(OUTPUT_DIR, f"free_alert_{today}.md")
        with open(alert_path, "w", encoding="utf-8") as f:
            f.write(free_alert)
        logger.info(f"免费提醒已保存: {alert_path}")

    # ---- Step 6: 推送到公众号 ----
    wechat_published = False
    wechat_error = ""
    try:
        # 检查凭证是否配置
        get_access_token()  # 未配置或 IP 未加白时会抛出

        wc_article = WeChatArticle(
            title=f"🎮 今日游戏好价 | {datetime.now().strftime('%m月%d日')}",
            content=article,
            author="游戏好价Agent",
            digest=f"Steam {len(steam_deals)}个折扣 · Epic {len(epic_free)}个免费" if steam_deals or epic_free else "今日游戏好价速览",
        )

        result = publish_article(wc_article)
        if result.success:
            wechat_published = True
            logger.info(f"✅ 公众号已发布: publish_id={result.publish_id}")
        else:
            wechat_error = result.error or "未知错误"
            logger.warning(f"❌ 公众号发布失败: {wechat_error}")
    except WeChatError as e:
        wechat_error = str(e)
        if "not in whitelist" in str(e):
            logger.warning("⚠️ 公众号 IP 白名单未配置，跳过发布")
        else:
            logger.warning(f"⚠️ 公众号发布跳过: {e}")
    except Exception as e:
        wechat_error = str(e)
        logger.warning(f"⚠️ 公众号发布异常: {e}")

    # ---- Step 7: 生成统计摘要（供 cron return） ----
    summary = (
        f"📊 游戏折扣日报 | {datetime.now().strftime('%Y-%m-%d')}\n"
        f"\n"
    )
    if steam_deals:
        top_discounts = sorted(steam_deals, key=lambda d: d.discount_percent, reverse=True)[:3]
        summary += "🔥 Steam 特惠:\n"
        for d in top_discounts:
            summary += f"  -{d.discount_percent}% {d.name} ({d.final_price})\n"
    else:
        summary += "⚠️ Steam 数据暂不可达\n"

    if epic_free:
        summary += "\n🎁 Epic 本周免费:\n"
        for d in epic_free:
            summary += f"  🆓 {d.name}\n"

    summary += f"\n📝 文章已生成: {digest_path}"

    if wechat_published:
        summary += f"\n✅ 公众号已发布"
    elif wechat_error:
        summary += f"\n❌ 公众号发布失败: {wechat_error[:60]}"

    return summary


def main():
    """入口函数"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    result = run_daily_digest()
    print(result)


if __name__ == "__main__":
    main()
