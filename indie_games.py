#!/usr/bin/env python3
"""Curate indie games and fetch prices/images."""
import json, os, sys, httpx
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROXY = "socks5://127.0.0.1:7891"

# Curated indie games list
GAMES = [
    ("🎮 像素冒险 · 小而美", "#e74c3c", "Stardew Valley", "星露谷物语", 413150),
    ("🎮 像素冒险 · 小而美", "#e74c3c", "Terraria", "泰拉瑞亚", 105600),
    ("🎮 像素冒险 · 小而美", "#e74c3c", "Hollow Knight", "空洞骑士", 367520),
    ("🎨 手绘风 · 治愈系", "#e67e22", "Gris", "格瑞斯", 683320),
    ("🎨 手绘风 · 治愈系", "#e67e22", "Cuphead", "茶杯头", 268910),
    ("🎨 手绘风 · 治愈系", "#e67e22", "Spiritfarer", "灵魂旅人", 972660),
    ("🕹️ 独立神作 · 必玩", "#27ae60", "Celeste", "蔚蓝", 504230),
    ("🕹️ 独立神作 · 必玩", "#27ae60", "Undertale", "传说之下", 391540),
    ("🕹️ 独立神作 · 必玩", "#27ae60", "Hades", "哈迪斯", 1145320),
]

def fetch_games():
    with httpx.Client(proxy=PROXY, timeout=15, http2=False) as c:
        result = []
        for section, color, en_name, cn_name, appid in GAMES:
            try:
                r = c.get("https://store.steampowered.com/api/appdetails",
                         params={"appids": appid, "cc": "CN", "l": "schinese"})
                d = r.json().get(str(appid), {}).get("data", {})
                if d:
                    price = d.get("price_overview", {})
                    if price:
                        final = price.get("final", 0)
                        initial = price.get("initial", 0)
                        disc = price.get("discount_percent", 0)
                        final_cur = f"¥{final/100:.1f}" if final else "免费"
                        if disc > 0:
                            final_cur = f"¥{final/100:.1f} <span style='text-decoration:line-through;color:#999'>¥{initial/100:.1f} -{disc}%</span>"
                        else:
                            final_cur = f"¥{final/100:.1f}" if final else "免费游玩"
                    else:
                        final_cur = "免费游玩"
                    result.append({
                        "appid": appid,
                        "section": section,
                        "color": color,
                        "en_name": en_name,
                        "cn_name": cn_name,
                        "display_name": f"{en_name} / {cn_name}",
                        "final_price": final_cur,
                        "header_image": d.get("header_image", ""),
                        "short_description": (d.get("short_description", "") or "")[:200],
                        "price": final_cur,
                    })
            except Exception as e:
                print(f"  Failed {appid}: {e}")
    return result

def main():
    print("Fetching game data...")
    games = fetch_games()
    print(f"Fetched {len(games)} games")
    return games

if __name__ == "__main__":
    main()
