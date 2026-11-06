#!/usr/bin/env bash
# 本地一键生成：需要 Node.js >= 18 与 git
set -euo pipefail
M3U="${M3U_URL:-https://iptv-org.github.io/iptv/index.m3u}"
EPG_REPO="${EPG_REPO:-.epg-src}"

if [ ! -d "$EPG_REPO" ]; then
  git clone --depth 1 https://github.com/iptv-org/epg.git "$EPG_REPO"
  (cd "$EPG_REPO" && npm install --no-audit --no-fund)
fi

python3 scripts/build_channels.py --m3u "$M3U" --epg-repo "$EPG_REPO" \
  --out build/channels.xml --report build/report.json --max-per-channel "${MAX_PER_CHANNEL:-1}"

(cd "$EPG_REPO" && npm run grab -- \
  --channels=../build/channels.xml --output=../build/guide.xml \
  --maxConnections="${MAX_CONNECTIONS:-8}" --days="${DAYS:-3}")

python3 scripts/postprocess.py build/guide.xml public/epg.xml \
  --channels build/channels.xml --gzip
python3 scripts/make_index.py public --report build/report.json

echo "完成：public/epg.xml.gz"
echo "本地预览：npx serve public   ->  http://localhost:3000/epg.xml.gz"
