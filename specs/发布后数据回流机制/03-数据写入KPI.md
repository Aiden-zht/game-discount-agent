---
title: "发布后数据回流机制 - 数据写入 KPI"
date: "2026-06-10"
tags: [公众号, 数据回流, 反馈闭环, KPI]
category: "业务/写作/公众号/创作规范"
domain: writing
platform: 公众号
load: workflow
audience: [agent]
provides: [KPI写入, 数据结构, 写入逻辑]
status: active
synopsis: "发布后数据回流机制 - 数据写入 KPI：业务/写作/公众号/创作规范 的流程规范，说明执行步骤、约束和检查点。"
version: 2
changelog: "kpi.json 路径改为 Agent 本地 ~/.hermes/skills/game-discount-agent/state/"
versions:
  KPI写入: 1
  数据结构: 1
  写入逻辑: 1
---

## 3. 数据写入 KPI

### 3.1 数据结构扩展

在 Agent 本地状态目录 `~/.hermes/skills/game-discount-agent/state/kpi.json` 中维护 `performance` 字段：

> **路径说明**：KPI 状态文件是 Agent 本地运行时数据，不属于知识库。存放在 Agent 技能目录内，不在 KB 仓库 `references/agent_mem/` 中。

```json
{
    "agent_a": { ... },
    "agent_b": { ... },
    "performance": {
        "total_articles": 47,
        "avg_read_count": 320,
        "avg_share_count": 12,
        "best_article": {
            "title": "今日折扣精选 | 06-10",
            "read_count": 1200,
            "share_count": 45,
            "tags": ["史低", "Epic限免"]
        },
        "worst_article": {
            "title": "xxx",
            "read_count": 80,
            "share_count": 1,
            "tags": ["攻略"]
        },
        "by_type": {
            "daily-digest": {"avg_read": 350, "avg_share": 15, "count": 30},
            "single-game": {"avg_read": 280, "avg_share": 8, "count": 12},
            "epic-free": {"avg_read": 500, "avg_share": 25, "count": 5}
        },
        "by_tag": {
            "史低": {"avg_read": 420, "count": 20},
            "限免": {"avg_read": 550, "count": 8},
            "攻略": {"avg_read": 180, "count": 10}
        },
        "recent_10": [
            {"title": "xxx", "reads": 320, "shares": 10, "date": "2026-06-10"}
        ]
    }
}
```

### 3.2 写入逻辑

