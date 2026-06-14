---
title: "Agent A：内容开发"
date: "2026-06-10"
tags: [公众号, 发布流程, AgentA, 自检]
category: "业务/写作/公众号/创作规范"
domain: writing
platform: 公众号
load: workflow
audience: [agent]
provides: ["AgentA公众号内容开发流程", "AgentA自检清单A1-A14"]
status: active
synopsis: "Agent A：内容开发：业务/写作/公众号/创作规范 的流程规范，说明执行步骤、约束和检查点。"
version: 4
changelog: "[Agent自修] 新增 A13-A14：主题配图匹配与列表 HTML 安全自检"
versions:
  AgentA公众号内容开发流程: 4
  AgentA自检清单A1-A14: 1
---

# Agent A：内容开发

## 2.1 职责

Agent A 负责内容的抓取、生成和初步渲染。**必须在输出 state JSON 前完成自检**。

## 2.2 标准流程

实际执行流程：

```bash
# 1. 抓取 + 生成 + 上传配图 + 生成 HTML
python3 {{WORKSPACE}}/tools/game-discount-agent/cron_digest.py

# 2. 产出: output/state.json（含 self_check 结果）
# 3. 校验: delegate_task + game-content-validator
# 4. 发布: python3 {{WORKSPACE}}/tools/game-discount-agent/publish_draft.py
```

完整流水线步骤解耦为：

```
cron_digest.py（scrape+build）→ delegate_task(validate) → publish_draft.py(publish)
```

## 2.3 Agent A 自检清单（14 项）

Agent A 在提交给 Agent B 之前，必须自行检查以下项目：

| # | 检查项 | 规则 | 严重级别 |
|---|--------|------|----------|
| A1 | **HTML 非空** | content 字段不为空且长度 > 100 字符 | BLOCKING |
| A2 | **标题存在** | title 字段非空，长度 5-64 字符 | BLOCKING |
| A3 | **封面图存在** | thumb_media_id 非空，且对应的上传状态为 SUCCESS | BLOCKING |
| A4 | **配图 URL 有效** | 所有 img src 以 `https://` 开头，非空，且非占位文本（如 `待上传`） | BLOCKING |
| A5 | **HTML 基本结构** | 包含 `<body>` 标签，标签正确闭合 | BLOCKING |
| A6 | **内容与标题一致** | 正文前 200 字包含标题中的关键词 | WARNING |
| A7 | **无裸露 URL** | 正文中无未包裹的 `http://` 文本 | WARNING |
| A8 | **段落长度** | 单段不超过 200 字（手机屏 5-6 行） | WARNING |
| A9 | **图片上传状态全检** | state.json 中每张图片的 `upload_status` 均为 SUCCESS 或 FALLBACK，不允许 FAILED | BLOCKING |
| A10 | **图片数量一致** | HTML 中 `<img>` 标签数量 = state.json `images` 中 `upload_status=SUCCESS` 的图片数量 | BLOCKING |
| A11 | **无空 src** | 所有 `<img>` 标签的 `src` 属性非空，且不包含 `{{`、`待填写`、`占位` 等模板标记 | BLOCKING |
| A12 | **图片-游戏映射正确** | 每张非封面图（game_id != `__cover__`）的 game_id 在 games 列表中真实存在；且 HTML 中该游戏区块附近（前后 200 字符）至少出现 1 张该 game_id 的图片 | BLOCKING |
| A13 | **配图主题匹配** | 非游戏主题文章不得使用游戏封面、Steam header、游戏截图；知识库治理/Agent 工作流/技术方法论类文章优先使用流程图、架构图、信息图或无图排版 | BLOCKING |
| A14 | **列表 HTML 安全** | 最终 HTML 不得残留 Markdown 列表语法；`<ul>/<ol>` 内不得有空 `<li>`、空 `<p>`、连续 `<br>`，列表间距必须用 CSS margin 控制 | BLOCKING |

## 2.4 输出格式

Agent A 输出的 state JSON 必须包含：

```json
{
    "type": "daily_digest | thematic",
    "title": "文章标题",
    "content": "<html>...</html>",
    "thumb_media_id": "封面图 media_id",
    "digest": "摘要（64字以内）",
    "images": [
        {
            "id": "header_01",
            "game_id": "__cover__",
            "game_name": null,
            "type": "header",
            "source_url": "https://steamcdn.akamaihd.net/steam/...",
            "cdn_url": "https://mmbiz.qpic.cn/...",
            "upload_status": "SUCCESS",
            "upload_error": null,
            "retry_count": 0,
            "fallback_used": false
        },
        {
            "id": "screenshot_01",
            "game_id": "730",
            "game_name": "Counter-Strike 2",
            "type": "screenshot",
            "source_url": "...",
            "cdn_url": "...",
            "upload_status": "SUCCESS",
            "upload_error": null,
            "retry_count": 1,
            "fallback_used": false
        }
    ],
    "self_check": {
        "passed": true,
        "blocking_count": 0,
        "warning_count": 2,
        "items": [
            {"code": "A1", "status": "PASS"},
            {"code": "A6", "status": "WARNING", "detail": "正文前200字未包含标题关键词"}
        ]
    },
    "status": "ready_for_review",
    "created_at": "2026-06-10T10:00:00"
}
```
