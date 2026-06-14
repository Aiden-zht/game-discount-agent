---
business: "游戏折扣文章自动生成与发布"
domain: [writing]
description: "Steam/Epic 游戏折扣信息的微信公众号文章自动生成、审核、配图和发布"
depends_on: [Agent行为约束, 写作通用规范索引]
provides: [游戏折扣文章发布流程, 公众号API, 游戏折扣文章风格, 配图治理, Steam特殊版本处理]
kb_refresh_policy: runtime
created: "2026-06-11"
---

# 游戏折扣文章自动生成与发布

## 任务类型

- 发布游戏折扣文章：定时/手动触发的完整流水线（爬取→筛选→生成→审查→配图→发布）
- 创建新类型公众号文章：用户指定主题，Agent 按流程创作

## 依赖的 Memento 规范

- `Agent行为约束` → [[规章制度/知识库管理/知识库内容治理规范/07-Agent行为约束]]
- `写作通用规范索引` → [[知识/写作方法论/index]]

## 目录

- `rules/` — 发布流程、质量规范、合规要求
- `references/` — API 手册、文章模板、风格库
