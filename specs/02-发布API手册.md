---
title: "公众号API开发手册"
date: "2026-06-10"
tags: [公众号, API, 开发, 素材管理, 草稿]
category: "业务/写作/公众号/创作规范"
domain: writing
platform: 公众号
load: index
audience: [agent]
provides: [公众号API开发手册索引]
status: active
synopsis: "公众号API开发手册：业务/写作/公众号/创作规范 的导航入口，帮助 Agent 快速定位相关文件。"
version: 1
changelog: "initial"
versions:
  公众号API开发手册索引: 1
---

# 公众号 API 开发手册

> 微信公众平台 API 完整使用指南：从 access_token 到文章发布

API 详情（素材管理、草稿、发布、用户、消息、菜单）见子文档：[[业务/写作/公众号/创作规范/公众号API开发手册/API参考]]

---

## 1. 基础概念

### 1.1 API 架构

```
你的服务器 → 微信 API 服务器 → 微信客户端
                ↑
          access_token 认证
```

### 1.2 核心接口地址

| 接口 | 地址 | 方法 |
|------|------|------|
| 获取 token | `https://api.weixin.qq.com/cgi-bin/token` | GET |
| 上传永久素材 | `https://api.weixin.qq.com/cgi-bin/material/add_material` | POST |
| 上传临时素材 | `https://api.weixin.qq.com/cgi-bin/media/upload` | POST |
| 获取素材列表 | `https://api.weixin.qq.com/cgi-bin/material/batchget_material` | POST |
| 新建草稿 | `https://api.weixin.qq.com/cgi-bin/draft/add` | POST |
| 获取草稿列表 | `https://api.weixin.qq.com/cgi-bin/draft/batchget` | POST |
| 发布 | `https://api.weixin.qq.com/cgi-bin/freepublish/submit` | POST |
| 用户列表 | `https://api.weixin.qq.com/cgi-bin/user/get` | GET |
| 模板消息 | `https://api.weixin.qq.com/cgi-bin/message/template/send` | POST |
| 自定义菜单 | `https://api.weixin.qq.com/cgi-bin/menu/create` | POST |

---

## 2. Access Token 管理

### 2.1 获取方式

```python
import httpx

def get_access_token(appid, appsecret):
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": appsecret,
    }
    resp = httpx.get(url, params=params)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    raise Exception(f"获取 token 失败: {data}")
```

### 2.2 注意事项

| 规则 | 说明 |
|------|------|
| 有效期 | 2 小时（7200 秒） |
| 每日上限 | 2000 次 |
| 缓存策略 | 必须缓存，重复获取会触发频率限制 |
| 过期处理 | 提前 5 分钟刷新，避免请求时恰好过期 |
| IP 限制 | 调用方 IP 必须在白名单中 |

### 2.3 缓存实现

```python
import time

class TokenManager:
    def __init__(self, appid, appsecret):
        self.appid = appid
        self.appsecret = appsecret
        self._token = None
        self._expires_at = 0

    def get_token(self):
        if time.time() < self._expires_at - 300:
            return self._token
        self._token = get_access_token(self.appid, self.appsecret)
        self._expires_at = time.time() + 7200
        return self._token
```

---

## 3. 完整发布流水线示例

以游戏折扣日报为例的完整流程：

```python
# 1. 获取 token
token_mgr = TokenManager(APPID, APPSECRET)
token = token_mgr.get_token()

# 2. 上传封面图
thumb_id = upload_material(token, "cover.jpg", "thumb")["media_id"]

# 3. 上传文章配图（CDN 方式）
img_url = upload_image_for_article(token, "game_screenshot.jpg")

# 4. 构建文章 HTML
html = f"""
<div style="...">
  <h2>今日好价</h2>
  <img src="{img_url}" style="width:100%"/>
  <p>游戏介绍...</p>
</div>
"""

# 5. 创建草稿
article = Article(
    title="🎮 今日游戏折扣精选",
    content=html,
    thumb_media_id=thumb_id,
    author="大钱",
    digest="精选今日 Steam/Epic 折扣游戏",
)
media_id = create_draft(token, [article])

# 6. 发布（需要认证权限）
result = publish(token, media_id)
print(f"发布ID: {result.get('publish_id')}")
```

---

## 4. 错误处理最佳实践

```python
def safe_api_call(func, *args, **kwargs):
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            result = func(*args, **kwargs)
            errcode = result.get("errcode", 0)
            if errcode == 0:
                return result
            if errcode == 40001:
                token_mgr._token = None
                continue
            if errcode == 45009:
                time.sleep(60)
                continue
            return result
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    return {"errcode": -1, "errmsg": "max retries exceeded"}
```

---

## 相关文档

- [[业务/写作/公众号/创作规范/公众号API开发手册/API参考]] — 素材管理、草稿、发布、用户、消息、菜单
- [[业务/写作/公众号/创作规范/04-文章模板]] — 文章 HTML 排版模板
- [[业务/写作/公众号/创作规范/03-平台合规细则]] — 审核机制、违规规避
- [[业务/写作/公众号/项目文档/index]] — 本 API 的实际应用项目
