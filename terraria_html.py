#!/usr/bin/env python3
"""Generate Terraria article HTML and save to file."""
import os, json, sys, httpx

# Read state (images already uploaded to WeChat CDN)
state_path = "/mnt/data/daqian-ai-workshop/creation/publication-terraria/terraria_state.json"
with open(state_path) as f:
    state = json.load(f)
header_url = state["header_cdn_url"]
ss_urls = state["screenshot_cdn_urls"]

# Build image section
ss_html = ""
for u in ss_urls:
    ss_html += f'<p style="margin:12px 0"><img src="{u}" style="width:100%;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1)"/></p>\n'

# Full article HTML with rich layout
html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,\"Helvetica Neue\",\"PingFang SC\",\"Microsoft YaHei\",sans-serif;background:#fff;color:#333;">

<!-- Cover Section -->
<div style="position:relative;width:100%;height:320px;overflow:hidden;border-radius:0 0 12px 12px;margin-bottom:20px">
  <img src="{header_url}" style="width:100%;height:100%;object-fit:cover;display:block" alt="Terraria Cover"/>
  <div style="position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(0,0,0,0.7));padding:30px 20px 20px">
    <h1 style="margin:0 0 6px 0;font-size:28px;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,0.5);line-height:1.3">喜欢泰拉瑞亚的人，<br/>都希望有一个没玩过泰拉瑞亚的脑子</h1>
    <p style="margin:0;font-size:14px;color:rgba(255,255,255,0.8)">大钱 · 2026年6月</p>
  </div>
</div>

<!-- Lead Section -->
<div style="padding:0 16px 16px">
  <blockquote style="border-left:4px solid #4a90d9;padding:12px 16px;margin:16px 0;background:#f0f7ff;border-radius:0 8px 8px 0;font-style:italic;color:#555;line-height:1.8">
    人们常说，喜欢泰拉瑞亚的人都希望有一个没玩过泰拉瑞亚的脑子。<br/>
    这话乍一听像骂人，但玩过的人都会心一笑。
  </blockquote>

  <p>因为泰拉瑞亚真的<b>太好了好</b>。</p>

  <p>好到你一旦玩了它，其他游戏都像在将就。好到你和女朋友一玩就是十几个小时，她喊累你喊还不够。好到别人问你玩什么游戏，你说不出来，只说"一个像素风的小游戏"，对方露出困惑的表情——而你知道他们永远不会懂。</p>
</div>

<!-- What Is -->
<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:24px 16px 12px;padding-bottom:8px;border-bottom:3px solid #4a90d9">泰拉瑞亚到底是什么？</h2>
<div style="padding:0 16px 16px">
  <p>Steam 上的介绍只有七个字：</p>
  <div style="text-align:center;padding:16px;margin:16px 0;background:linear-gradient(135deg,#667eea11,#764ba211);border-radius:12px">
    <span style="font-size:22px;font-weight:bold;color:#667eea;letter-spacing:2px">挖掘 · 战斗 · 探索 · 建造</span>
  </div>
  <p>就这么简单。像素画面，2D 视角，看起来像是手机上的一个小游戏。</p>
  <p>但只有真正开始玩的人才会发现——这是一个<b>世界</b>。你不是在"玩一个游戏"，你是在一个<b>完全属于你的世界</b>里活着。</p>
</div>

<!-- Gameplay Loop -->
<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:24px 16px 12px;padding-bottom:8px;border-bottom:3px solid #4a90d9">白天挖矿，晚上逃命</h2>
<div style="padding:0 16px 16px">
  <p>泰拉瑞亚的节奏很独特：</p>

  <div style="background:#f8f9fa;border-radius:10px;padding:14px;margin:12px 0;border-left:4px solid #3498db">
    <b style="color:#3498db">☀️ 白天</b>——拿着一把破木剑和一把铁镐，在森林里砍树、挖矿、收集资源。挖到铁就造铁剑，挖到铜就造铜甲。
  </div>

  <div style="background:#f8f9fa;border-radius:10px;padding:14px;margin:12px 0;border-left:4px solid #2ecc71">
    <b style="color:#2ecc71">🌆 傍晚</b>——开始准备装备：火把、药水、武器、盔甲。每一次夜晚都是一次冒险。
  </div>

  <div style="background:#f8f9fa;border-radius:10px;padding:14px;margin:12px 0;border-left:4px solid #e74c3c">
    <b style="color:#e74c3c">🌙 夜晚</b>——怪物从四面八方涌来，Boss 会刷新，你需要逃跑、战斗、或者硬刚。第一次被史莱姆追着跑的时候，我慌得连火把都不会放。
  </div>
</div>

<!-- Screenshot Gallery -->
<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:24px 16px 12px;padding-bottom:8px;border-bottom:3px solid #4a90d9">看看这个像素世界</h2>
<div style="padding:0 16px 16px">
  {ss_html}
</div>

<!-- Why It's Special -->
<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:24px 16px 12px;padding-bottom:8px;border-bottom:3px solid #4a90d9">最让我上头的三个地方</h2>
<div style="padding:0 16px 16px">
  <h3 style="font-size:15px;font-weight:bold;color:#e74c3c;margin:16px 0 8px">1. 你真的在"建造"</h3>
  <p>很多游戏说"建造"，其实是搭积木。泰拉瑞亚不一样——你的家真的是你<b>亲手</b>一砖一瓦盖起来的。从一个小木屋开始，到地下基地，到空中城堡，到地下城市。</p>

  <h3 style="font-size:15px;font-weight:bold;color:#e74c3c;margin:16px 0 8px">2. 你永远不知道下一秒会发生什么</h3>
  <p>你刚挖到一个金箱子，里面是完美的武器；你刚走到一片空地，脚下突然塌穿，掉进地下湖；你刚击败了一个 Boss，抬头一看，月亮正在升起——而新的 Boss 正在倒计时。</p>
  <p>这种<b>未知感</b>是泰拉瑞亚的灵魂。每次玩都能发现新东西。</p>

  <h3 style="font-size:15px;font-weight:bold;color:#e74c3c;margin:16px 0 8px">3. 和女朋友一起玩，真的幸福</h3>
  <p>我和女朋友一起玩的。她负责建设和规划，我负责打怪和收集。分工明确，效率极高。她比我慢一步——但她的房子比我好看多了。</p>
  <p>最让我感动的是，她本来没玩过，但玩了之后比我玩得更认真。她会花好几个小时摆装饰，会在凌晨两点告诉我"我发现了新地图"，会在我打 Boss 的时候紧张得喊出声。</p>
  <p>泰拉瑞亚不是"两个人各玩各的"，而是一起在一个世界里冒险。</p>
</div>

<!-- Epic Journey -->
<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:24px 16px 12px;padding-bottom:8px;border-bottom:3px solid #4a90d9">从像素到史诗</h2>
<div style="padding:0 16px 16px">
  <p>刚开始你以为你在玩一个像素小游戏。玩到中期，你发现自己已经在打世纪之敌——那个让全服玩家又爱又恨的最终 Boss。</p>
  <p>中间经历了很多：第一次掉进地狱的恐惧，第一次打败机械三王的不敢置信，第一次拿到真银时的狂喜。</p>
  <p><b>泰拉瑞亚的好，不在于画面有多精致，而在于它给你的每一次探索都是真的。</b></p>
  <p>你不是在看别人怎么玩，你不是在刷任务列表。你是在<b>自己的世界</b>里，一寸一寸地前进。</p>
</div>

<!-- Punchline -->
<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:24px 16px 12px;padding-bottom:8px;border-bottom:3px solid #4a90d9">为什么我说它的脑子有问题？</h2>
<div style="padding:0 16px 16px">
  <p>因为玩过泰拉瑞亚的人，再去看其他游戏的时候，脑子里总会比较：</p>
  <p>"这个游戏的探索感有泰拉瑞亚好吗？""这个建造系统能自己盖东西吗？""这个 Boss 设计有世纪之敌那么刺激吗？"</p>
  <p>最后发现，<b>大部分游戏都比不上</b>。</p>
  <p>所以人们开玩笑说——喜欢泰拉瑞亚的人都希望有一个没玩过泰拉瑞亚的脑子。</p>
  <p style="font-size:18px;color:#e74c3c;font-weight:bold;text-align:center;margin:20px 0">因为只有没玩过的人，才不会失望。</p>
</div>

<!-- Info Card -->
<div style="margin:24px 16px 16px;background:linear-gradient(135deg,#4a90d9,#667eea);border-radius:12px;padding:20px;color:#fff">
  <h3 style="margin:0 0 12px 0;font-size:16px">🎮 Terraria · 泰拉瑞亚</h3>
  <div style="display:flex;flex-wrap:wrap;gap:8px">
    <span style="background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:4px;font-size:13px">类型：2D 沙盒冒险</span>
    <span style="background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:4px;font-size:13px">开发商：Re-Logic</span>
    <span style="background:rgba(255,255,255,0.2);padding:4px 10px;border-radius:4px;font-size:13px">支持：单人 / 多人合作</span>
  </div>
  <p style="margin:12px 0 0 0;font-size:13px;opacity:0.9">Steam: <a href="https://store.steampowered.com/app/105600/" style="color:#fff;text-decoration:underline" target="_blank">https://store.steampowered.com/app/105600/</a></p>
</div>

<!-- Footer -->
<div style="padding:16px;border-top:1px solid #eee;margin-top:16px">
  <p style="font-size:12px;color:#bbb;text-align:center">如果觉得好，别忘了分享给你身边还没玩过泰拉瑞亚的朋友 🎮</p>
</div>

</body></html>'''

# Save HTML
html_dir = "/mnt/data/daqian-ai-workshop/creation/publication-terraria"
os.makedirs(html_dir, exist_ok=True)
html_path = os.path.join(html_dir, "terraria_article.html")
with open(html_path, "w") as f:
    f.write(html)
print(f"HTML saved: {html_path} ({len(html)} bytes)")
sys.exit(0)
