#!/usr/bin/env python3
"""Upload game header images to WeChat permanent material."""

import http.client
import json
import logging
import os
import tempfile
import time
from typing import Optional
from steam_scraper import GameDeal
import httpx

logger = logging.getLogger(__name__)


class WeChatImageUploader:
    """下载游戏封面图 → 上传到微信永久素材 → 返回微信 CDN URL"""

    def __init__(self):
        self._http: Optional[httpx.Client] = None
        self._cache: dict[int, str] = {}  # appid → wechat_url

    def _get_http(self) -> httpx.Client:
        if self._http is None:
            proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or None
            if proxy:
                self._http = httpx.Client(timeout=20, proxy=proxy)
            else:
                self._http = httpx.Client(timeout=20)
        return self._http

    def _download_image(self, url: str) -> bytes:
        """Download image from URL (e.g. Steam CDN)."""
        resp = self._get_http().get(url)
        resp.raise_for_status()
        return resp.content

    def _upload_to_wechat(self, image_data: bytes, token: str) -> str:
        """Upload image bytes to WeChat permanent material. Returns WeChat CDN URL."""
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        body_parts = [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="media"; filename="game.jpg"\r\n',
            b"Content-Type: image/jpeg\r\n",
            b"\r\n",
            image_data,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        body = b"".join(body_parts)

        conn = http.client.HTTPSConnection("api.weixin.qq.com", timeout=20)
        conn.request(
            "POST",
            f"/cgi-bin/material/add_material?access_token={token}&type=image",
            body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()

        if "url" in data:
            return data["url"]
        else:
            raise RuntimeError(f"WeChat upload failed: {data}")

    def process_game_images(
        self, games: list[GameDeal], token: str
    ) -> dict[int, str]:
        """Batch download+upload game header images. Returns {appid: wechat_url}."""
        results = {}
        for i, g in enumerate(games):
            if g.appid in self._cache:
                results[g.appid] = self._cache[g.appid]
                continue

            # Steam header image (most reliable format)
            url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{g.appid}/header.jpg"

            try:
                logger.info(f"Downloading [{i+1}/{len(games)}] {g.name}...")
                img_data = self._download_image(url)
                logger.info(f"  {len(img_data)} bytes, uploading to WeChat...")
                wechat_url = self._upload_to_wechat(img_data, token)
                self._cache[g.appid] = wechat_url
                results[g.appid] = wechat_url
                logger.info(f"  ✅ WeChat CDN: {wechat_url[:40]}...")
            except Exception as e:
                # Try smaller capsule format as fallback
                try:
                    alt_url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{g.appid}/capsule_231x87.jpg"
                    logger.info(f"  Retrying with capsule format for {g.name}...")
                    img_data = self._download_image(alt_url)
                    wechat_url = self._upload_to_wechat(img_data, token)
                    self._cache[g.appid] = wechat_url
                    results[g.appid] = wechat_url
                    logger.info(f"  ✅ WeChat CDN (capsule): {wechat_url[:40]}...")
                except Exception as e2:
                    logger.warning(f"  ❌ {g.name}: header.jpg + capsule both failed")
                    # 不移入 image_map，让 content_generator 显示占位符
                    continue

            # Small delay to avoid rate limits (WeChat: 500/day)
            if i < len(games) - 1:
                time.sleep(0.5)

        return results

    def close(self):
        if self._http:
            self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("WeChat Image Uploader module loaded.")