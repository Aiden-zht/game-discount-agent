---
title: "KPI 评分规则"
date: "2026-06-10"
tags: [公众号, KPI, 评分, 质量]
category: "业务/写作/公众号/创作规范"
domain: writing
platform: 公众号
load: workflow
audience: [agent]
provides: ["发布流程KPI评分规则"]
status: active
synopsis: "KPI 评分规则：业务/写作/公众号/创作规范 的流程规范，说明执行步骤、约束和检查点。"
version: 1
changelog: "initial"
versions:
  发布流程KPI评分规则: 1
---

# KPI 评分规则

> **评分框架参考**：评分维度、权重配置见
> [[业务/写作/通用/07-KPI评分通用框架]]

## 6.1 Agent A（开发者）评分

| 项目 | 分值 | 说明 |
|------|------|------|
| 基础分 | 100 | 每次发布起始分 |
| BLOCKING 项 | -5/项 | 每个 BLOCKING 项扣分 |
| WARNING 项 | -1/项 | 每个 WARNING 项扣分 |
| 完美通过 | +10 | 首次提交 0 BLOCKING + 0 WARNING |
| 修复成功 | +3 | 经修复后通过审查 |

## 6.2 Agent B（审查者）评分

| 项目 | 分值 | 说明 |
|------|------|------|
| 基础分 | 100 | 每次审查起始分 |
| 检出 BLOCKING | +5/项 | 成功检出的 BLOCKING 项 |
| 漏检 BLOCKING | -10/项 | Agent A 自检标记通过但 Agent B 检出为 BLOCKING 的问题 |
| 完美审查 | +5 | 审查报告准确、详细 |

## 6.3 评分存储

评分记录保存到 `state.json` 的 `kpi` 字段：

```json
{
    "kpi": {
        "agent_a": {"score": 98, "blocking": 0, "warning": 2, "bonuses": []},
        "agent_b": {"score": 105, "detected": 2, "missed": 0, "bonuses": ["perfect_review"]}
    }
}
```
