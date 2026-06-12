#!/usr/bin/env python3
"""Step 1: Scrape & Upload images for WeChat article.

Usage: python3 terraria_scrape.py [APPID] [IMAGES_DIR] [STATE_FILE]
"""

import os, sys, json, io
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import httpx
from PIL import Image
from wechat_publisher import get_access_token

PROXY = "socks5://127.0.0.1:7891"

def upload_to_wechat(token, content, filename, media_type="image"):
    """Upload image to WeChat CDN."""
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    parts = []
    for line in [f"--{boundary}\r\n",
                  f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n',
                  f"Content-Type: image/jpeg\r\n", "\r\n"]:
        parts.append(line.encode())
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    with httpx.Client(timeout=30) as c:
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type={media_type}"
        r = c.post(url, content=body,
                   headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        data = r.json()
        if media_type == "image":
            return data.get("url", "")
        return data.get("media_id", "")

def scrape_app_images(appid, images_dir):
    """Download header + screenshots from Steam, upload to WeChat CDN."""
    header_url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
    
    with httpx.Client(proxy=PROXY, timeout=30, http2=False) as c:
        r = c.get(f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese")
        app_data = r.json().get(str(appid), {}).get("data", {})
    
    screenshots = app_data.get("screenshots", [])[:6]
    
    with httpx.Client(proxy=PROXY, timeout=30, http2=False) as c:
        r = c.get(header_url)
        header_data = r.content
    
    token = get_access_token()
    header_url_cdn = upload_to_wechat(token, header_data, "header.jpg")
    
    ss_urls = []
    for i, ss in enumerate(screenshots):
        ss_url = ss.get("path_full", "")
        if ss_url:
            with httpx.Client(proxy=PROXY, timeout=30, http2=False) as c:
                r = c.get(ss_url)
                ss_data = r.content
            cdn = upload_to_wechat(token, ss_data, f"ss_{i+1}.jpg")
            if cdn:
                ss_urls.append(cdn)
    
    return header_url_cdn, ss_urls, header_data

def main(appids=None, images_dir="", state_file=""):
    if not appids:
        print("Usage: python3 terraria_scrape.py [APPID] [IMAGES_DIR] [STATE_FILE]")
        return 1
        
    appid = int(appids[0])
    
    print(f"Downloading images for AppID {appid}...")
    header_url, ss_urls, header_data = scrape_app_images(appid, images_dir or "")
    
    # Upload thumb (300x200 center-crop)
    img = Image.open(io.BytesIO(header_data))
    w, h = img.size
    target_ratio = 300 / 200
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        img = img.crop(((w - new_w)//2, 0, (w + new_w)//2, h))
    else:
        new_h = int(w / target_ratio)
        img = img.crop((0, (h - new_h)//2, w, (h + new_h)//2))
    img = img.resize((300, 200), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    
    token = get_access_token()
    thumb_id = upload_to_wechat(token, buf.getvalue(), "thumb.png", "thumb")
    
    state = {
        "type": "thematic",
        "appid": appid,
        "header_cdn_url": header_url,
        "screenshot_cdn_urls": ss_urls,
        "thumb_media_id": thumb_id,
        "scraped_at": datetime.now().isoformat(),
        "html_path": None,
    }
    
    os.makedirs(os.path.dirname(state_file) or ".", exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f"Scraped & uploaded:")
    print(f"   Header CDN: {header_url[:50]}...")
    print(f"   Screenshots: {len(ss_urls)}")
    print(f"   Thumb: {thumb_id[:30]}...")
    print(f"   State: {state_file}")
    
    return 0

if __name__ == "__main__":
    appids = sys.argv[1:2]
    images_dir = sys.argv[2:3]
    state_file = sys.argv[3:4]
    sys.exit(main(appids, images_dir[0] if images_dir else "", state_file[0] if state_file else ""))
