---
name: version-id
version: "1.0.0"
description: "All published WeChat articles must include a short version ID for session/agent identification."
---

# Version ID 规范 — 版本标识

## 目的

每次发表（发草稿/发文章）的文章末尾必须包含版本 ID，用于肉眼区分是哪个 session/agent 发表的哪一版。

## 格式

`YYMMDD-六位十六进制随机串`

例如：`260610-a3f8c2`、`260610-b7e1d4`

- `YYMMDD` = 日期（两位年份 + 两位月 + 两位日）
- 后 6 位十六进制 = 同日内随机串，~167 万种组合

## 渲染位置

HTML 文章末尾，footer 之后：

```html
<p style="font-size:10px;color:#ccc;text-align:right;padding-top:8px">Version: V260610-a3f8c2</p>
```

样式：10px 字号，浅灰色，靠右对齐，不影响正文阅读。

## 代码实现

### cron_digest.py（折扣日报）

Phase 1 构建时生成：
```python
today_short = datetime.now().strftime("%y%m%d")
rand_hex = f"{random.randint(0, 0xFFFFFF):06x}"
version_id = f"{today_short}-{rand_hex}"
```

传给 content_generator：
```python
article_html = generator.generate_daily_digest(unique, [], image_map=image_map, version_id=version_id)
```

写入 state JSON：
```python
state = { ..., "version_id": version_id, }
```

### content_generator.py

`ArticleGenerator.generate_daily_digest()` 的 signature 增加 `version_id: str = ""` 参数。

在 HTML 末尾渲染：
```python
parts.append(
    '<p style="font-size:10px;color:#ccc;text-align:right;padding-top:8px">Version: V' + version_id + '</p>'
)
```

空文章（无数据）的提前 return 中也附加版本 ID。

## 校验规则

- 校验者（Agent B）检查 HTML 末尾是否包含 `Version: V` 开头的行
- 格式必须是 `VYYMMDD-xxxxxx`（V + 6位数字 + 横杠 + 6位十六进制）
- 不匹配 = WARNING
