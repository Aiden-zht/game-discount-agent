import re
import unittest

from content_generator import ArticleGenerator
from steam_scraper import GameDeal, SteamScraper


class DeadlineTests(unittest.TestCase):
    def test_api_item_to_deal_uses_item_discount_expiration_as_deadline(self):
        scraper = SteamScraper()
        item = {
            "id": 123,
            "name": "Deadline Test",
            "original_price": 10000,
            "final_price": 5000,
            "discount_percent": 50,
            "discount_expiration": 1781625600,  # 2026-06-16 16:00 UTC = 2026-06-17 CST
        }

        deal = scraper._api_item_to_deal(item)

        self.assertEqual(deal.deadline, "2026年06月17日")

    def test_daily_digest_shows_each_game_own_deadline_not_global_deadline(self):
        deals = [
            GameDeal(
                appid=1,
                name="Game A",
                name_en="Game A",
                name_cn="游戏A",
                original_price_cents=10000,
                final_price_cents=5000,
                discount_percent=50,
                review_score=90,
                deadline="2026年06月17日",
            ),
            GameDeal(
                appid=2,
                name="Game B",
                name_en="Game B",
                name_cn="游戏B",
                original_price_cents=10000,
                final_price_cents=4000,
                discount_percent=60,
                review_score=90,
                deadline="2026年06月20日",
            ),
        ]

        html = ArticleGenerator().generate_daily_digest(deals, [], version_id="TEST")

        self.assertNotIn("优惠截止时间：", html)
        self.assertNotIn("每款游戏截止日期见卡片，具体以 Steam 商店页面为准", html)
        self.assertIn("截止：2026年06月17日", html)
        self.assertIn("截止：2026年06月20日", html)
        self.assertRegex(html, re.compile(r"Game A[\s\S]*截止：2026年06月17日"))
        self.assertRegex(html, re.compile(r"Game B[\s\S]*截止：2026年06月20日"))


if __name__ == "__main__":
    unittest.main()
