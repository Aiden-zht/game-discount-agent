#!/usr/bin/env python3
"""
WeChat Official Account publisher for game discount agent.

Flow: get access_token → create draft (草稿) → publish draft (发布)

Environment variables:
  WECHAT_APPID     - AppID from mp.weixin.qq.com
  WECHAT_APPSECRET - AppSecret from mp.weixin.qq.com

Prerequisites:
  Server IP must be added to IP whitelist at mp.weixin.qq.com → 开发 → 基本配置
"""

import os
import sys
import json
import time
import logging
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Ensure we can import sibling modules when run standalone
sys.path.insert(0, str(Path(__file__).parent.resolve()))

# httpx for HTTP requests (already in requirements.txt)
import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
PUBLISH_URL = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"

# Token cache (valid for 7200s, refresh at 6000s)
_token_cache: dict = {"token": None, "expires_at": 0}


class WeChatError(Exception):
    """WeChat API returned an error."""
    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"[{errcode}] {errmsg}")


@dataclass
class Article:
    """A single article to publish."""
    title: str
    content: str
    author: str = "游戏好价Agent"
    digest: str = ""
    content_source_url: str = ""
    thumb_media_id: str = ""
    need_open_comment: int = 0
    only_fans_can_comment: int = 0


@dataclass
class PublishResult:
    """Result of a publish operation."""
    success: bool
    publish_id: Optional[str] = None
    article_url: Optional[str] = None
    error: Optional[str] = None
    draft_media_id: Optional[str] = None


def _get_credentials() -> tuple[str, str]:
    """Get AppID and AppSecret from environment."""
    appid = os.environ.get("WECHAT_APPID", "")
    secret = os.environ.get("WECHAT_APPSECRET", "")
    
    # Fallback: try .env file
    if not appid or not secret:
        env_paths = [
            "/root/.hermes/.env",
            Path(__file__).parent / ".env",
        ]
        for env_path in env_paths:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("WECHAT_APPID=") and not appid:
                            appid = line.split("=", 1)[1]
                        elif line.startswith("WECHAT_APPSECRET=") and not secret:
                            secret = line.split("=", 1)[1]
                if appid and secret:
                    break
    
    return appid, secret


def get_access_token(force_refresh: bool = False) -> str:
    """
    Get WeChat API access_token with caching.
    Token is valid for 7200s; refresh at 6000s.
    """
    global _token_cache
    
    now = time.time()
    if not force_refresh and _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    
    appid, secret = _get_credentials()
    if not appid or not secret:
        raise WeChatError(-1, "WECHAT_APPID or WECHAT_APPSECRET not set")
    
    params = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    }
    
    with httpx.Client(timeout=15) as client:
        resp = client.get(TOKEN_URL, params=params)
        data = resp.json()
    
    if "access_token" in data:
        _token_cache["token"] = data["access_token"]
        # Refresh at 6000s to avoid edge-of-expiry race conditions
        _token_cache["expires_at"] = now + max(data.get("expires_in", 7200) - 1200, 600)
        return _token_cache["token"]
    else:
        errcode = data.get("errcode", -1)
        errmsg = data.get("errmsg", "Unknown error")
        raise WeChatError(errcode, errmsg)


def create_draft(article: Article, client: Optional[httpx.Client] = None) -> str:
    """
    Create a draft (草稿) from article content.
    Returns media_id for use in publish.
    """
    token = get_access_token()
    
    # Build article payload
    article_data = {
        "title": article.title,
        "author": article.author,
        "digest": article.digest or article.title,
        "content": article.content,
        "need_open_comment": article.need_open_comment,
        "only_fans_can_comment": article.only_fans_can_comment,
    }
    if article.content_source_url:
        article_data["content_source_url"] = article.content_source_url
    if article.thumb_media_id:
        article_data["thumb_media_id"] = article.thumb_media_id
    
    payload = {"articles": [article_data]}
    
    close_client = False
    if client is None:
        client = httpx.Client(timeout=30)
        close_client = True
    
    try:
        resp = client.post(
            DRAFT_ADD_URL,
            params={"access_token": token},
            json=payload,
        )
        data = resp.json()
        
        if "media_id" in data:
            logger.info(f"Draft created: media_id={data['media_id']}")
            return data["media_id"]
        else:
            errcode = data.get("errcode", -1)
            errmsg = data.get("errmsg", "Unknown error")
            raise WeChatError(errcode, errmsg)
    finally:
        if close_client:
            client.close()


def publish_draft(media_id: str, client: Optional[httpx.Client] = None) -> PublishResult:
    """
    Publish a draft via freepublish/submit.
    Returns publish result with publish_id.
    """
    token = get_access_token()
    payload = {"media_id": media_id}
    
    close_client = False
    if client is None:
        client = httpx.Client(timeout=30)
        close_client = True
    
    try:
        resp = client.post(
            PUBLISH_URL,
            params={"access_token": token},
            json=payload,
        )
        data = resp.json()
        
        if data.get("errcode") == 0:
            publish_id = data.get("publish_id", "")
            logger.info(f"Publish submitted: publish_id={publish_id}")
            return PublishResult(
                success=True,
                publish_id=publish_id,
                draft_media_id=media_id,
            )
        else:
            errcode = data.get("errcode", -1)
            errmsg = data.get("errmsg", "Unknown error")
            logger.error(f"Publish failed: [{errcode}] {errmsg}")
            return PublishResult(
                success=False,
                error=f"[{errcode}] {errmsg}",
                draft_media_id=media_id,
            )
    finally:
        if close_client:
            client.close()


def check_publish_status(publish_id: str, client: Optional[httpx.Client] = None) -> dict:
    """
    Check the status of a publish submission.
    """
    token = get_access_token()
    
    close_client = False
    if client is None:
        client = httpx.Client(timeout=15)
        close_client = True
    
    try:
        resp = client.post(
            "https://api.weixin.qq.com/cgi-bin/freepublish/get",
            params={"access_token": token},
            json={"publish_id": publish_id},
        )
        return resp.json()
    finally:
        if close_client:
            client.close()


def publish_article(article: Article) -> PublishResult:
    """
    Full publish flow: create draft → publish draft.
    """
    try:
        # Step 1: Create draft
        logger.info(f"Creating draft: {article.title}")
        media_id = create_draft(article)
        
        # Step 2: Publish draft
        logger.info(f"Publishing draft: {media_id}")
        result = publish_draft(media_id)
        
        if result.success:
            logger.info(f"Published successfully: publish_id={result.publish_id}")
        else:
            logger.error(f"Publish failed: {result.error}")
        
        return result
        
    except WeChatError as e:
        logger.error(f"WeChat API error: {e}")
        return PublishResult(success=False, error=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return PublishResult(success=False, error=str(e))


def main():
    """Command-line entry point: test the publisher with a sample article."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    print("=== WeChat Publisher Test ===")
    
    # Step 1: Test credentials / access_token
    print("\n1. Testing access_token...")
    try:
        token = get_access_token()
        print(f"   ✓ Token obtained: {token[:10]}...{token[-5:]}")
    except WeChatError as e:
        print(f"   ✗ Failed: {e}")
        print("\n   Common causes:")
        print("   - Server IP not whitelisted at mp.weixin.qq.com → 开发 → 基本配置 → IP白名单")
        print("   - AppID or AppSecret incorrect")
        sys.exit(1)
    
    # Step 2: Create a sample draft
    print("\n2. Creating sample draft...")
    article = Article(
        title="🎮 今日游戏好价 | Steam & Epic 折扣精选",
        content="<h2>今日折扣速览</h2>"
        "<p>Steam 和 Epic 今日折扣已更新，来看看有哪些值得入手的好游戏。</p>"
        "<h3>Steam 精选</h3>"
        "<ul>"
        "<li><b>游戏A</b> - 原价 ¥100 现价 ¥30 (-70%)</li>"
        "<li><b>游戏B</b> - 原价 ¥80 现价 ¥24 (-70%)</li>"
        "</ul>"
        "<h3>Epic 免费游戏</h3>"
        "<ul>"
        "<li><b>免费游戏X</b> - 本周限免，原价 ¥60</li>"
        "</ul>"
        "<p>关注 游戏好价Agent，每日推送最值得买的游戏！</p>",
        author="游戏好价Agent",
        digest="每日 Steam + Epic 游戏折扣精选，帮你省钱买好游戏",
    )
    
    try:
        media_id = create_draft(article)
        print(f"   ✓ Draft created: media_id={media_id}")
    except WeChatError as e:
        print(f"   ✗ Failed: {e}")
        sys.exit(1)
    
    # Step 3: Publish
    print("\n3. Publishing draft...")
    result = publish_draft(media_id)
    if result.success:
        print(f"   ✓ Published! publish_id={result.publish_id}")
        print(f"   → 文章已发布到公众号，可在后台查看")
    else:
        print(f"   ✗ Failed: {result.error}")
        sys.exit(1)
    
    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    main()
