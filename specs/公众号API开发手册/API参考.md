---
title: "公众号API开发手册 - API参考"
date: "2026-06-10"
tags: [公众号, API, 开发, 素材管理, 草稿]
category: "业务/写作/公众号/创作规范/公众号API开发手册"
domain: writing
platform: 公众号
load: on-demand
audience: [agent]
provides: [公众号API参考, 素材管理API, 草稿API, 发布API]
status: active
synopsis: "公众号API开发手册 - API参考：业务规范/参考，说明 公众号 API 参考 子文档：素材管理、草稿管理、发布接口、用户管理、消息管理、菜单管理的 API 详情。 完整概念和发。"
version: 1
changelog: "initial"
versions:
  公众号API参考: 1
  素材管理API: 1
  草稿API: 1
  发布API: 1
---

# 公众号 API 参考

> **子文档**：素材管理、草稿管理、发布接口、用户管理、消息管理、菜单管理的 API 详情。
>
> 完整概念和发布流水线见主文档 [[业务/写作/公众号/创作规范/公众号API开发手册/index]]

---

## 素材管理

### 素材类型

| 类型 | 说明 | 永久保存 | 数量限制 |
|------|------|:---:|----------|
| `image` | 图片 | ✅ | 5000 张 |
| `voice` | 语音 | ✅ | 2000 个 |
| `video` | 视频 | ✅ | 500 个 |
| `thumb` | 缩略图 | ✅ | 5000 个 |
| `news` | 图文消息 | ✅ | 5000 篇 |

### 上传永久素材

```python
def upload_material(token, filepath, media_type="image"):
    """上传永久素材"""
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material"
    params = {"access_token": token, "type": media_type}
    
    with open(filepath, "rb") as f:
        files = {"media": (filepath.split("/")[-1], f)}
        resp = httpx.post(url, params=params, files=files)
    
    return resp.json()
    # 成功返回: {"media_id": "xxx", "url": "https://mmbiz.qpic.cn/..."}
```

### 上传图片到文章 CDN（非永久素材）

```python
def upload_image_for_article(token, filepath):
    """上传图片供文章使用（返回 URL，不占用永久素材额度）"""
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg"
    params = {"access_token": token}
    
    with open(filepath, "rb") as f:
        files = {"media": (filepath.split("/")[-1], f)}
        resp = httpx.post(url, params=params, files=files)
    
    return resp.json().get("url", "")
```

### 获取素材列表

```python
def list_materials(token, media_type="image", offset=0, count=20):
    """获取永久素材列表"""
    url = "https://api.weixin.qq.com/cgi-bin/material/batchget_material"
    params = {"access_token": token}
    data = {"type": media_type, "offset": offset, "count": count}
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
```

### 删除素材

```python
def delete_material(token, media_id):
    """删除永久素材"""
    url = "https://api.weixin.qq.com/cgi-bin/material/del_material"
    params = {"access_token": token}
    data = {"media_id": media_id}
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
```

---

## 草稿管理

### 创建草稿

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Article:
    title: str           # 标题（必填，64字以内）
    content: str         # 正文 HTML（必填）
    thumb_media_id: str  # 封面图 media_id（必填）
    author: str = ""     # 作者
    digest: str = ""     # 摘要（64字以内，不填则自动截取）
    content_source_url: str = ""  # 原文链接
    need_open_comment: int = 0    # 是否打开评论（0关闭 1打开）
    only_fans_can_comment: int = 0  # 是否仅粉丝可评论

def create_draft(token, articles: List[Article]):
    """创建草稿（返回 media_id）"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/add"
    params = {"access_token": token}
    
    articles_data = []
    for a in articles:
        articles_data.append({
            "title": a.title,
            "author": a.author,
            "digest": a.digest,
            "content": a.content,
            "thumb_media_id": a.thumb_media_id,
            "content_source_url": a.content_source_url,
            "need_open_comment": a.need_open_comment,
            "only_fans_can_comment": a.only_fans_can_comment,
        })
    
    data = {"articles": articles_data}
    resp = httpx.post(url, params=params, json=data)
    result = resp.json()
    return result.get("media_id", "")
```

### 修改草稿

```python
def update_draft(token, media_id, index, article: Article):
    """修改草稿中的某篇文章"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/update"
    params = {"access_token": token}
    data = {
        "media_id": media_id,
        "index": index,
        "articles": {
            "title": article.title,
            "author": article.author,
            "digest": article.digest,
            "content": article.content,
            "thumb_media_id": article.thumb_media_id,
            "content_source_url": article.content_source_url,
        }
    }
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
```

### 获取草稿列表

```python
def list_drafts(token, offset=0, count=20):
    """获取草稿列表"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/batchget"
    params = {"access_token": token}
    data = {"offset": offset, "count": count, "no_content": 0}
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
```

### 删除草稿

```python
def delete_draft(token, media_id):
    """删除草稿"""
    url = "https://api.weixin.qq.com/cgi-bin/draft/delete"
    params = {"access_token": token}
    data = {"media_id": media_id}
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
```

---

## 发布接口

### 提交发布

```python
def publish(token, media_id):
    """发布草稿（提交后进入审核队列）"""
    url = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
    params = {"access_token": token}
    data = {"media_id": media_id}
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
    # 成功: {"publish_id": "123"}
    # 失败: {"errcode": 48001, "errmsg": "api unauthorized"}
```

### 发布状态查询

```python
def get_publish_status(token, publish_id):
    """查询发布状态"""
    url = "https://api.weixin.qq.com/cgi-bin/freepublish/get"
    params = {"access_token": token}
    data = {"publish_id": publish_id}
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
    # publish_status: 0-成功 1-发布中 2-原创审核 3-常规审核
```

### 常见错误码

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| `48001` | 功能未授权 | 确认已认证；或使用草稿接口替代 |
| `40001` | access_token 无效 | 检查 token 是否过期、IP 白名单 |
| `40004` | 无效的媒体文件类型 | 检查 media_type 参数 |
| `45009` | API 调用次数超限 | 等待次日重置 |
| `45005` | 超过字数限制 | 缩短标题/摘要 |

> **注意**：`freepublish/submit` 接口处于灰度阶段，部分账号（含个人订阅号）可能未开通。未开通的账号返回 48001 api unauthorized，但仍可通过 API 创建草稿（draft/add），然后手动在公众号后台完成发布。

---

## 用户管理

### 获取用户列表

```python
def get_followers(token, next_openid=""):
    """获取关注者列表"""
    url = "https://api.weixin.qq.com/cgi-bin/user/get"
    params = {"access_token": token, "next_openid": next_openid}
    
    resp = httpx.get(url, params=params)
    return resp.json()
```

### 获取用户信息

```python
def get_user_info(token, openid, lang="zh_CN"):
    """获取用户详细信息"""
    url = "https://api.weixin.qq.com/cgi-bin/user/info"
    params = {"access_token": token, "openid": openid, "lang": lang}
    
    resp = httpx.get(url, params=params)
    return resp.json()
```

### 批量获取用户信息

```python
def batch_get_user_info(token, openid_list):
    """批量获取用户信息（最多 100 个）"""
    url = "https://api.weixin.qq.com/cgi-bin/user/info/batchget"
    params = {"access_token": token}
    data = {
        "user_list": [{"openid": oid, "lang": "zh_CN"} for oid in openid_list]
    }
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json().get("user_info_list", [])
```

---

## 消息管理

### 客服消息

```python
def send_customer_message(token, openid, content):
    """发送客服消息（48小时内有互动的用户）"""
    url = "https://api.weixin.qq.com/cgi-bin/message/custom/send"
    params = {"access_token": token}
    data = {
        "touser": openid,
        "msgtype": "text",
        "text": {"content": content}
    }
    
    resp = httpx.post(url, params=params, json=data)
    return resp.json()
```

### 模板消息（服务号）

```python
def send_template_message(token, openid, template_id, data, url=""):
    """发送模板消息"""
    api_url = "https://api.weixin.qq.com/cgi-bin/message/template/send"
    params = {"access_token": token}
    payload = {
        "touser": openid,
        "template_id": template_id,
        "url": url,
        "data": data,
    }
    
    resp = httpx.post(api_url, params=params, json=payload)
    return resp.json()
```

---

## 菜单管理

### 创建自定义菜单

```python
def create_menu(token, menu_data):
    """创建自定义菜单"""
    url = "https://api.weixin.qq.com/cgi-bin/menu/create"
    params = {"access_token": token}
    
    resp = httpx.post(url, params=params, json=menu_data)
    return resp.json()
```

### 菜单结构示例

```json
{
    "button": [
        {
            "type": "click",
            "name": "今日折扣",
            "key": "DAILY_DEALS"
        },
        {
            "type": "view",
            "name": "历史好价",
            "url": "https://mp.weixin.qq.com/xxx"
        },
        {
            "name": "更多",
            "sub_button": [
                {"type": "click", "name": "搜索游戏", "key": "SEARCH_GAME"},
                {"type": "click", "name": "联系客服", "key": "CONTACT"}
            ]
        }
    ]
}
```

---

## 相关文档

- [[业务/写作/公众号/创作规范/公众号API开发手册/index]] — 基础概念、发布流水线、错误处理
