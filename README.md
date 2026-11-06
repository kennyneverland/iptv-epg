# IPTV 节目单（EPG）生成器

把 `https://iptv-org.github.io/iptv/index.m3u`（或你自己的 M3U）里的频道，
自动映射到 [iptv-org/epg](https://github.com/iptv-org/epg) 的抓取源，生成一份可订阅的 XMLTV 节目单。

部署完成后，你的订阅地址是：

```
https://<你的GitHub用户名>.github.io/<仓库名>/epg.xml.gz
```

每天自动更新一次，播放器里填一次就不用再管。

---

## 一、先搞清楚一件事

- `iptv-org.github.io/epg` 这个站点**已经不再托管节目单**（访问返回 404），
  `iptv-org/epg` 仓库本身只是**抓取工具**，不提供现成的订阅地址。
- 所以想给 index.m3u 配节目单，只有两条路：自己跑抓取器生成，或找第三方聚合站
  （第三方站的频道 id 和 iptv-org 的 `tvg-id` 对不上，播放器里照样没节目单）。
- **实测（2026-11-06）**：index.m3u 共 3642 个频道，其中 **1336 个（36.7%）**
  能在 epg 仓库找到对应抓取源，涉及 94 个站点。剩下 63% 的频道官方就没有 EPG 源，
  任何方案都补不出来。

本仓库做的事就是：**M3U → 匹配抓取源 → 抓取 → 合并去重 → 托管成一个订阅地址**。

## 二、三步部署（GitHub Pages，免费）

1. **建仓库**：在 GitHub 新建一个仓库（public 或 private 都行），把本目录全部文件推上去。

   ```bash
   git init -b main
   git add .
   git commit -m "init epg builder"
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```

2. **开 Pages**：仓库 → Settings → Pages → Build and deployment → Source 选
   **GitHub Actions**（不要选 Deploy from a branch）。

3. **跑一次**：仓库 → Actions → 左侧 `Build EPG` → Run workflow。
   首次约 30–90 分钟（94 个站点、1336 个频道，逐站抓取），跑完在
   `https://<用户名>.github.io/<仓库名>/` 就能看到订阅地址。

之后每天 UTC 02:00（北京时间 10:00）自动重跑，节目单自动刷新。

## 三、订阅地址怎么填

| 播放器 | 填哪里 |
| --- | --- |
| TiviMate | 设置 → EPG → 添加 EPG 源 → 填 `.../epg.xml.gz` |
| DIYP / 电视家类 | EPG 接口 / 节目单地址 |
| Kodi (PVR IPTV Simple) | EPG Settings → XMLTV URL |
| Emby / Jellyfin | 直播电视 → 电视指南数据提供商 → XMLTV |

**关键点**：节目单靠 `tvg-id` 和播放列表里的频道对应。本仓库生成的 XMLTV 里，
频道 id 就是 index.m3u 里的 `tvg-id`（例如 `CCTV1.cn@SD`），所以**必须配同一份 M3U**，
换播放列表就要重新生成。

## 四、自定义

在仓库 Settings → Secrets and variables → Actions → **Variables** 里加：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `M3U_URL` | `https://iptv-org.github.io/iptv/index.m3u` | 换成你自己的播放列表地址（支持 http/https） |
| `MAX_PER_CHANNEL` | `1` | 每个频道保留几个抓取源。调大更全但更慢，也更容易出现重复节目 |
| `MAX_CONNECTIONS` | `8` | 并发请求数。站点限流时调小到 2–4 |
| `DAYS` | `3` | 抓几天节目单。调大文件更大、耗时更长 |

只想要某类频道（例如只做中文频道），在本地生成清单时加过滤：

```bash
python3 scripts/build_channels.py --m3u https://iptv-org.github.io/iptv/index.m3u \
  --group '中国|香港|台湾|澳门' -o build/channels.xml
```

`--group` 匹配 `group-title`，`--id` 匹配 `tvg-id`，都支持正则。

## 五、本地 / NAS 运行

```bash
bash scripts/run_local.sh          # 需要 Node.js >= 18、git、python3
npx serve public                   # 局域网访问 http://<本机IP>:3000/epg.xml.gz
```

想常驻就用官方镜像，自带每天定时刷新：

```bash
docker run -d --name epg -p 3000:3000 \
  -v "$PWD/build/channels.xml:/epg/public/channels.xml" \
  -e CRON_SCHEDULE="0 2 * * *" \
  -e MAX_CONNECTIONS=8 \
  ghcr.io/iptv-org/epg:master
# 订阅地址 http://<NAS地址>:3000/guide.xml
```

## 六、目录结构

```
.
├── scripts/
│   ├── build_channels.py    # M3U → channels.xml（匹配抓取源，含覆盖率统计）
│   ├── postprocess.py       # 去重、排序、补齐频道名、gzip
│   ├── make_index.py        # 生成订阅首页
│   └── run_local.sh         # 本地一键跑全流程
├── sample/
│   ├── channels.index-m3u.xml  # 已生成好的清单（index.m3u，1336 条），可直接喂给 grab
│   └── report.json             # 覆盖率统计
└── .github/workflows/epg.yml   # 每日自动构建 + 发布 Pages
```

## 七、常见问题

**跑完节目单是空的？**
看 Actions 日志里 `grab` 那一步。多数是某个站点改版或被限流，属于常态；
把 `MAX_CONNECTIONS` 降到 2–4 重跑，或减少频道范围。

**部分频道没节目单？**
63% 的 index.m3u 频道在 iptv-org/epg 里本来就没有抓取源，属于数据源缺失，不是脚本问题。

**想加某个台的节目单？**
到 `iptv-org/epg` 的 `sites/` 下看有没有该站的配置；没有就得自己写一个抓取器
（官方有贡献指南），或者换用带该台 EPG 的第三方源。

**文件多大？**
1336 个频道 × 3 天，压缩后通常几 MB，播放器加载无压力。
