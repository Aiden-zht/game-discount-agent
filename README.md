# 游戏折扣公众号 Agent

自动爬取 Steam / Epic 游戏折扣数据，AI 生成公众号文章。

## 项目结构

```
game-discount-agent/
├── steam_scraper.py      # Steam 折扣爬虫
├── epic_scraper.py       # Epic 免费游戏爬虫
├── content_generator.py  # AI 文章生成器（DeepSeek API / 模板备选）
├── wechat_publisher.py   # 公众号自动发布模块
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

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 否 | DeepSeek API Key，不填则使用模板模式 |
| `WECHAT_APPID` | 否 | 公众号 AppID，填了才会自动发布 |
| `WECHAT_APPSECRET` | 否 | 公众号 AppSecret |

## 公众号集成

文章生成后会自动尝试发布到公众号（流程：创建草稿 → 发布草稿）。

### 首次使用前

1. 注册公众号 [mp.weixin.qq.com](https://mp.weixin.qq.com)，个人免费
2. 在 开发 → 基本配置 中获取 AppID + AppSecret
3. **IP 白名单**：将服务器外网 IP 添加到 基本配置 → IP白名单
4. 配置环境变量 `WECHAT_APPID` + `WECHAT_APPSECRET`

之后每天 10:00 自动爬取 → 生成文章 → 发布到公众号，全程无人值守。
