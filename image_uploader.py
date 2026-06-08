#!/usr/bin/env python3
"""Upload game header images to WeChat permanent material / fallback parent image."""

import http.client
import json
import logging
import os
import time
from typing import Optional
from steam_scraper import GameDeal, PARENT_APPID_MAP
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

    def _try_download(self, appid: int, label: str) -> bytes | None:
        """尝试下载封面图：header.jpg → capsule_231x87.jpg"""
        urls = [
            f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg",
            f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/capsule_231x87.jpg",
        ]
        for url, fmt in zip(urls, ["header", "capsule"]):
            try:
                data = self._download_image(url)
                logger.info(f"  ✅ {fmt} OK ({len(data)} bytes)")
                return data
            except Exception:
                logger.info(f"  {fmt} 404, trying next...")
        return None

    def process_game_images(
        self, games: list[GameDeal], token: str
    ) -> dict[int, str]:
        """Batch download+upload game header images. Returns {appid: wechat_url}.

        URL 优先级：
        1. appdetails 提供的 header_image（CDN 带 hash，最准）
        2. 裸 URL patterns（header.jpg → capsule）
        3. PARENT_APPID_MAP → 母游戏封面（仅 DLC/Bundle）
        """
        results = {}
        for i, g in enumerate(games):
            if g.appid in self._cache:
                results[g.appid] = self._cache[g.appid]
                continue

            label = f"{g.name_en or g.name}" + (f" / {g.name_cn}" if g.name_cn else "")
            logger.info(f"Downloading [{i+1}/{len(games)}] {label}...")

            img_data = None

            # 1) appdetails 带 hash 的 header_image URL
            if g.header_image:
                try:
                    img_data = self._download_image(g.header_image)
                    logger.info(f"  ✅ appdetails URL ({len(img_data)} bytes)")
                except Exception:
                    logger.info(f"  appdetails URL failed, falling back...")

            # 2) 裸 URL
            if img_data is None:
                img_data = self._try_download(g.appid, label)

            # 3) DLC/Bundle → 母游戏
            if img_data is None and g.appid in PARENT_APPID_MAP:
                parent_id = PARENT_APPID_MAP[g.appid]
                logger.info(f"  → 用母游戏 appid {parent_id}")
                img_data = self._try_download(parent_id, f"{label} (parent)")

            if img_data is not None:
                try:
                    wechat_url = self._upload_to_wechat(img_data, token)
                    self._cache[g.appid] = wechat_url
                    results[g.appid] = wechat_url
                    logger.info(f"  ✅ WeChat CDN: {wechat_url[:40]}...")
                except Exception as e:
                    logger.warning(f"  ❌ WeChat upload failed: {e}")
            else:
                logger.warning(f"  ❌ {label}: all attempts failed, placeholder will be used")

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