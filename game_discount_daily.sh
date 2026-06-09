#!/bin/bash
# 游戏折扣日报 Phase 1 包装脚本
# 检查代理可用性后运行爬虫

set -e

cd /mnt/data/daqian-ai-workshop/tools/game-discount-agent || {
  echo "ERROR: game-discount-agent 目录不存在"
  exit 1
}

TODAY=$(date '+%Y%m%d')
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] === 游戏折扣日报 Phase 1 ==="

# 检查 SOCKS5 代理
if curl -sI --max-time 5 --proxy socks5://127.0.0.1:7891 https://store.steampowered.com 2>/dev/null | grep -q "HTTP/"; then
    echo "[$TIMESTAMP] SOCKS5 代理可用"
else
    echo "[$TIMESTAMP] SOCKS5 代理不可用，尝试直连..."
    if curl -sI --max-time 5 https://store.steampowered.com 2>/dev/null | grep -q "HTTP/"; then
        echo "[$TIMESTAMP] Steam 直连可达"
    else
        echo "[$TIMESTAMP] Steam 不可达，放弃本次运行"
        exit 1
    fi
fi

# 运行 Phase 1
python3 cron_digest.py 2>&1 || {
    echo "[$TIMESTAMP] Phase 1 失败"
    exit 1
}

echo "[$TIMESTAMP] === Phase 1 完成 ==="
