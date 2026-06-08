# 游戏折扣公众号 Agent

自动爬取 Steam / Epic 游戏折扣数据，AI 生成公众号文章。

## 项目结构

```
game-discount-agent/
├── steam_scraper.py      # Steam 折扣爬虫
├── epic_scraper.py       # Epic 免费游戏爬虫
├── content_generator.py  # AI 文章生成器（DeepSeek API / 模板备选）
├── cron_digest.py        # 每日流水线入口
├── requirements.txt      # 依赖
├── output/               # 生成的文章存储
├── .env.example          # 环境变量模板
└── README.md
```

## 使用方式

### 手动运行一次

```bash
cd /mnt/data/daqian-ai-workshop/tools/game-discount-agent
pip install -r requirements.txt
python3 cron_digest.py
```

### 定时任务（Hermes cron）

```bash
hermes cron create \
  --name "game-discount-daily" \
  --schedule "0 10 * * *" \
  --workdir /mnt/data/daqian-ai-workshop/tools/game-discount-agent \
  --command "python3 cron_digest.py"
```

每天早上10点自动生成。（北京时间）

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 否 | DeepSeek API Key，不填则使用模板模式 |

## 公众号集成

文章生成后存储在 `output/` 目录，格式为 markdown。

- 有 API Key：AI 写文，风格接地气带幽默
- 无 API Key：模板模式，纯数据展示

后续可接入公众号自动发布（需 AppID + AppSecret）。
