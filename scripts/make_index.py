#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 public/index.html：显示订阅地址与本次生成概况。"""
import argparse
import json
import os
from datetime import datetime, timezone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", nargs="?", default="public")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    stats = {}
    if args.report and os.path.exists(args.report):
        stats = json.load(open(args.report, encoding="utf-8"))

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    owner, _, name = repo.partition("/")
    base = f"https://{owner.lower()}.github.io/{name}/" if owner else ""
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = "".join(
        f"<li><code>{s}</code> — {n} 个频道</li>" for s, n in stats.get("top_sites", [])[:10]
    )

    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IPTV 节目单订阅</title>
<style>
 body{{margin:0;padding:48px 24px;font:16px/1.7 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
      background:#0f1115;color:#e8eaed}}
 .wrap{{max-width:760px;margin:0 auto}}
 h1{{font-size:26px;margin:0 0 8px}}
 .sub{{color:#9aa0a6;margin-bottom:32px}}
 .card{{background:#171a21;border:1px solid #262b36;border-radius:12px;padding:20px 22px;margin-bottom:18px}}
 .label{{color:#9aa0a6;font-size:13px;letter-spacing:.04em;text-transform:uppercase;margin-bottom:10px}}
 a.url{{color:#7cc4ff;word-break:break-all;font-size:17px;text-decoration:none}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}}
 .num{{font-size:24px;font-weight:600}}
 .k{{color:#9aa0a6;font-size:13px}}
 ul{{margin:8px 0 0;padding-left:20px;color:#c7cbd1}}
 li{{margin:3px 0}}
 code{{background:#22262f;padding:1px 6px;border-radius:4px;font-size:13px}}
</style></head><body><div class="wrap">
<h1>IPTV 节目单</h1>
<div class="sub">由 iptv-org/epg 抓取生成 · 最后更新 {updated}</div>

<div class="card">
  <div class="label">订阅地址（XMLTV / EPG）</div>
  <a class="url" href="epg.xml.gz">{base}epg.xml.gz</a>
</div>

<div class="card">
  <div class="label">本次概况</div>
  <div class="grid">
    <div><div class="num">{stats.get('playlist_channels','-')}</div><div class="k">播放列表频道</div></div>
    <div><div class="num">{stats.get('covered_channels','-')}</div><div class="k">有节目单的频道</div></div>
    <div><div class="num">{stats.get('coverage_pct','-')}%</div><div class="k">覆盖率</div></div>
    <div><div class="num">{stats.get('sites','-')}</div><div class="k">抓取站点</div></div>
  </div>
</div>

<div class="card">
  <div class="label">贡献最多的站点</div>
  <ul>{rows or '<li>暂无</li>'}</ul>
</div>
</div></body></html>
"""
    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"index.html -> {args.outdir}")


if __name__ == "__main__":
    main()
