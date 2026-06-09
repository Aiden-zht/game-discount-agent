#!/usr/bin/env python3
"""
WeChat Official Account publisher for game discount agent.

Flow: 
  1. upload_thumb() → get thumb_media_id (permanent material)
  2. create_draft() → create draft with thumb (works for all accounts)
  3. publish_draft() → submit for publication (requires beta access, may fail 48001)
  4. If publish fails, draft is still saved in 草稿箱 for manual publish

Environment variables:
  WECHAT_APPID     - AppID from mp.weixin.qq.com
  WECHAT_APPSECRET - AppSecret from mp.weixin.qq.com

Prerequisites:
  Server IP must be added to IP whitelist at mp.weixin.qq.com → 开发 → 基本配置
"""

import os
import sys
import time
import logging
import struct
import zlib
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
import httpx

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
PUBLISH_URL = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
MATERIAL_ADD_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"

THUMB_DIR = Path(__file__).parent / "assets"
THUMB_PATH = THUMB_DIR / "thumb_default.png"

_token_cache: dict = {"token": None, "expires_at": 0}
_thumb_cache: dict = {"media_id": None, "checked": False}


class WeChatError(Exception):
    def __init__(self, errcode: int, errmsg: str):
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"[{errcode}] {errmsg}")


@dataclass
class Article:
    title: str
    content: str
    author: str = "好价Agent"
    digest: str = ""
    content_source_url: str = ""
    thumb_media_id: str = ""
    need_open_comment: int = 0
    only_fans_can_comment: int = 0


@dataclass
class PublishResult:
    success: bool
    publish_id: Optional[str] = None
    draft_saved: bool = False
    draft_media_id: Optional[str] = None
    error: Optional[str] = None


def upload_image_thumb(client: httpx.Client, token: str, image_url: str) -> str:
    """Download an image URL, crop to 300x200, upload as permanent thumb.
    Returns thumb_media_id.
    """
    from PIL import Image
    import io
    import httpx as _httpx

    # Download
    resp = _httpx.get(image_url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    img_bytes = resp.content

    # Resize to 300x200 center crop
    img = Image.open(io.BytesIO(img_bytes))
    # Calculate center crop
    w, h = img.size
    target_ratio = 300 / 200  # 1.5
    current_ratio = w / h

    if current_ratio > target_ratio:
        # Too wide: crop width
        new_w = int(h * target_ratio)
        offset = (w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, h))
    elif current_ratio < target_ratio:
        # Too tall: crop height
        new_h = int(w / target_ratio)
        offset = (h - new_h) // 2
        img = img.crop((0, offset, w, offset + new_h))

    img = img.resize((300, 200), Image.LANCZOS)

    # Save to PNG bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Upload as permanent thumb
    return _upload_material(client, token, png_bytes, "thumb_cover.png", "image/png")



def _upload_material(client: httpx.Client, token: str, file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload a file as permanent material, return media_id."""
    url = f"{MATERIAL_ADD_URL}?access_token={token}&type=thumb"
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body_parts = []
    for line in [
        f"--{boundary}\r\n",
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n',
        f"Content-Type: {content_type}\r\n",
        "\r\n",
    ]:
        body_parts.append(line.encode())
    body_parts.append(file_bytes)
    body_parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(body_parts)

    resp = client.post(
        url,
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if "media_id" in data:
        logger.info(f"✅ Thumb uploaded: {data['media_id'][:20]}...")
        return data["media_id"]
    raise WeChatError(data.get("errcode", -1), data.get("errmsg", "Upload failed"))


def _make_thumb_png() -> bytes:
    """Create a 300x200 dark-themed PNG thumbnail for articles."""
    w, h = 300, 200
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", 0xFFFFFFFF & zlib.crc32(b"IHDR" + ihdr_data))
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    raw = b""
    for y in range(h):
        raw += b"\x00"
        for x in range(w):
            raw += bytes([int(40+x*0.3), int(60+y*0.4), int(120+(x+y)*0.2)])
    compressed = zlib.compress(raw)
    idat_crc = struct.pack(">I", 0xFFFFFFFF & zlib.crc32(b"IDAT" + compressed))
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc
    iend_crc = struct.pack(">I", 0xFFFFFFFF & zlib.crc32(b"IEND"))
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    return sig + ihdr + idat + iend


def _get_credentials() -> tuple[str, str]:
    appid = os.environ.get("WECHAT_APPID", "")
    secret = os.environ.get("WECHAT_APPSECRET", "")
    if not appid or not secret:
        env_paths = ["/root/.hermes/.env", Path(__file__).parent / ".env"]
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


def _multipart_upload(client: httpx.Client, url: str, token: str, file_bytes: bytes, filename: str, content_type: str) -> dict:
    """Upload a file using multipart/form-data."""
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body_parts = []
    for line in [
        f"--{boundary}\r\n",
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n',
        f"Content-Type: {content_type}\r\n",
        "\r\n",
    ]:
        body_parts.append(line.encode())
    body_parts.append(file_bytes)
    body_parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(body_parts)
    
    resp = client.post(
        url,
        params={"access_token": token, "type": "thumb"},
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return resp.json()


def get_access_token(force_refresh: bool = False) -> str:
    global _token_cache
    now = time.time()
    if not force_refresh and _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    appid, secret = _get_credentials()
    if not appid or not secret:
        raise WeChatError(-1, "WECHAT_APPID or WECHAT_APPSECRET not set")
    with httpx.Client(timeout=15) as client:
        resp = client.get(TOKEN_URL, params={"grant_type": "client_credential", "appid": appid, "secret": secret})
        data = resp.json()
    if "access_token" in data:
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + max(data.get("expires_in", 7200) - 1200, 600)
        return _token_cache["token"]
    else:
        raise WeChatError(data.get("errcode", -1), data.get("errmsg", "Unknown error"))


def ensure_thumb(client: Optional[httpx.Client] = None) -> str:
    """
    Ensure we have a thumb_media_id for draft creation.
    Creates and uploads a default thumbnail if needed.
    """
    global _thumb_cache
    if _thumb_cache["media_id"] and _thumb_cache["checked"]:
        return _thumb_cache["media_id"]
    
    close_client = False
    if client is None:
        client = httpx.Client(timeout=30)
        close_client = True
    
    try:
        token = get_access_token()
        
        # Check if we already have a material
        resp = client.get(
            "https://api.weixin.qq.com/cgi-bin/material/get_materialcount",
            params={"access_token": token},
        )
        count_data = resp.json()
        has_existing = count_data.get("image_count", 0) > 0
        
        if has_existing:
            # Try to reuse first existing thumb
            resp2 = client.post(
                "https://api.weixin.qq.com/cgi-bin/material/batchget_material",
                params={"access_token": token},
                json={"type": "image", "offset": 0, "count": 1},
            )
            items = resp2.json().get("item", [])
            if items and "media_id" in items[0]:
                _thumb_cache["media_id"] = items[0]["media_id"]
                _thumb_cache["checked"] = True
                return _thumb_cache["media_id"]
        
        # Create and upload default thumb
        png_bytes = _make_thumb_png()
        logger.info(f"Uploading default thumbnail ({len(png_bytes)} bytes)...")
        
        upload_url = f"https://api.weixin.qq.com/cgi-bin/material/add_material"
        result = _multipart_upload(client, upload_url, token, png_bytes, "thumb_default.png", "image/png")
        
        if "media_id" in result:
            _thumb_cache["media_id"] = result["media_id"]
            _thumb_cache["checked"] = True
            logger.info(f"Thumb uploaded: {result['media_id'][:20]}...")
            return result["media_id"]
        else:
            raise WeChatError(result.get("errcode", -1), result.get("errmsg", "Thumb upload failed"))
    finally:
        if close_client:
            client.close()


def create_draft(article: Article, client: Optional[httpx.Client] = None) -> str:
    """
    Create a draft in WeChat 草稿箱 with a proper thumbnail.
    Returns media_id (this is saved as a draft for later manual or automatic publish).
    """
    token = get_access_token()
    close_client = False
    if client is None:
        client = httpx.Client(timeout=30)
        close_client = True
    
    try:
        # Get or create thumb
        thumb_id = article.thumb_media_id or ensure_thumb(client)
        
        article_data = {
            "title": article.title,
            "thumb_media_id": thumb_id,
            "author": article.author[:10],  # WeChat limits author to ~10 chars
            "digest": (article.digest or article.title)[:60],
            "content": article.content,
            "need_open_comment": article.need_open_comment,
            "only_fans_can_comment": article.only_fans_can_comment,
        }
        if article.content_source_url:
            article_data["content_source_url"] = article.content_source_url
        
        resp = client.post(
            DRAFT_ADD_URL,
            params={"access_token": token},
            json={"articles": [article_data]},
        )
        data = resp.json()
        
        if "media_id" in data:
            logger.info(f"Draft created: {data['media_id'][:20]}...")
            return data["media_id"]
        else:
            raise WeChatError(data.get("errcode", -1), data.get("errmsg", "Draft create failed"))
    finally:
        if close_client:
            client.close()


def publish_draft(media_id: str, client: Optional[httpx.Client] = None) -> PublishResult:
    """
    Publish a draft via freepublish/submit API.
    Note: This API requires the account to be in the 发布能力 beta (gray rollout).
    If it fails with 48001, the draft is still saved in 草稿箱 for manual publish.
    """
    token = get_access_token()
    close_client = False
    if client is None:
        client = httpx.Client(timeout=30)
        close_client = True
    
    try:
        resp = client.post(
            PUBLISH_URL,
            params={"access_token": token},
            json={"media_id": media_id},
        )
        data = resp.json()
        
        if data.get("errcode") == 0:
            pid = data.get("publish_id", "")
            logger.info(f"Published! publish_id={pid}")
            return PublishResult(success=True, publish_id=pid, draft_media_id=media_id, draft_saved=True)
        else:
            errcode = data.get("errcode", -1)
            errmsg = data.get("errmsg", "Unknown")
            logger.warning(f"Publish API not available [{errcode}]: {errmsg}")
            return PublishResult(
                success=False,
                draft_saved=True,
                draft_media_id=media_id,
                error=f"[{errcode}] {errmsg}",
            )
    finally:
        if close_client:
            client.close()


def publish_article(article: Article) -> PublishResult:
    """
    Full publish flow: create draft → attempt publish.
    Even if publish fails, the draft is saved in 草稿箱.
    """
    try:
        # Step 1: Create draft
        logger.info(f"Creating draft: {article.title}")
        media_id = create_draft(article)
        
        # Step 2: Attempt publish
        logger.info(f"Attempting to publish draft...")
        result = publish_draft(media_id)
        
        if result.success:
            logger.info(f"✓ Published: publish_id={result.publish_id}")
        else:
            logger.info(f"✓ Draft saved (media_id={media_id[:20]}...), publish deferred")
            logger.info(f"  Reason: {result.error}")
            logger.info(f"  → Go to mp.weixin.qq.com → 草稿箱 → click 发布")
        
        return result
    except WeChatError as e:
        logger.error(f"WeChat API error: {e}")
        return PublishResult(success=False, draft_saved=False, error=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return PublishResult(success=False, draft_saved=False, error=str(e))


def main():
    """CLI test: upload thumb → create draft → try publish."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 50)
    print("WeChat Publisher Test")
    print("=" * 50)
    
    # Step 1: Get token
    print("\n1. Getting access_token...")
    try:
        token = get_access_token()
        print("   ✓ Token obtained")
    except WeChatError as e:
        print(f"   ✗ {e}")
        sys.exit(1)
    
    # Step 2: Upload thumb
    print("\n2. Ensuring thumbnail...")
    try:
        thumb_id = ensure_thumb()
        print(f"   ✓ Thumb: {thumb_id[:20]}...")
    except WeChatError as e:
        print(f"   ✗ {e}")
        sys.exit(1)
    
    # Step 3: Create draft
    print("\n3. Creating test draft...")
    article = Article(
        title="今日游戏好价 | 测试",
        content="<h2>今日折扣</h2><p>Steam 折扣精选</p><ul><li>游戏A -70%</li><li>游戏B -75%</li></ul>",
        author="好价Agent",
        digest="每日游戏折扣精选",
    )
    try:
        media_id = create_draft(article)
        print(f"   ✓ Draft: {media_id[:20]}...")
    except WeChatError as e:
        print(f"   ✗ {e}")
        sys.exit(1)
    
    # Step 4: Try publish
    print("\n4. Attempting publish...")
    result = publish_draft(media_id)
    if result.success:
        print(f"   ✓ Published! publish_id={result.publish_id}")
    else:
        print(f"   ○ Draft saved, auto-publish not available yet")
        print(f"     Reason: {result.error}")
        print(f"     Action: Go to mp.weixin.qq.com → 草稿箱 → click 发布")
    
    print("\n" + "=" * 50)
    print("Done. Draft saved to 草稿箱 ✅")


if __name__ == "__main__":
    main()
