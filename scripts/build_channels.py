#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把任意 M3U 播放列表里的频道，映射到 iptv-org/epg 的抓取源，生成 channels.xml。

用法:
    python3 build_channels.py --m3u https://iptv-org.github.io/iptv/index.m3u -o build/channels.xml
    python3 build_channels.py --m3u my.m3u --epg-repo ../epg -o build/channels.xml --max-per-channel 1
"""
import argparse
import gzip
import io
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

RAW_BASE = "https://raw.githubusercontent.com/iptv-org/epg/master/"
TREE_API = "https://api.github.com/repos/iptv-org/epg/git/trees/master?recursive=1"

EXTINF_RE = re.compile(r"^#EXTINF:-?\d+(?:\.\d+)?\s+(.*?),(.*)$")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def fetch(url, timeout=30, retries=2):
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "epg-builder/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"下载失败 {url}: {last}")


def read_text(path_or_url):
    if re.match(r"^https?://", path_or_url):
        data = fetch(path_or_url, timeout=60)
    else:
        with open(path_or_url, "rb") as f:
            data = f.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8-sig", errors="replace")


def parse_m3u(text):
    """返回 [{id, name, group, url}]"""
    out = []
    pending = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            if not m:
                continue
            attrs = dict(ATTR_RE.findall(m.group(1)))
            pending = {
                "id": attrs.get("tvg-id", "").strip(),
                "name": m.group(2).strip(),
                "tvg_name": attrs.get("tvg-name", "").strip(),
                "group": attrs.get("group-title", "").strip(),
            }
        elif line.startswith("#"):
            continue
        elif pending is not None:
            pending["url"] = line
            out.append(pending)
            pending = None
    return out


def epg_repo_files(repo_dir, cache_dir):
    """返回本地 .channels.xml 路径列表：优先用本地仓库，否则从 GitHub 拉取并缓存。"""
    if repo_dir and os.path.isdir(repo_dir):
        files = []
        for root, _dirs, names in os.walk(repo_dir):
            for n in names:
                if n.endswith(".channels.xml"):
                    files.append(os.path.join(root, n))
        if files:
            log(f"[i] 使用本地仓库 {repo_dir}，找到 {len(files)} 个频道清单")
            return files

    os.makedirs(cache_dir, exist_ok=True)
    tree_path = os.path.join(cache_dir, "_tree.json")
    if os.path.exists(tree_path):
        tree = json.load(open(tree_path, encoding="utf-8"))
    else:
        tree = json.loads(fetch(TREE_API, timeout=60).decode("utf-8"))
        json.dump(tree, open(tree_path, "w", encoding="utf-8"))
    paths = [x["path"] for x in tree["tree"] if x["path"].endswith(".channels.xml")]

    def one(p):
        local = os.path.join(cache_dir, p.replace("/", "__"))
        if os.path.exists(local) and os.path.getsize(local) > 0:
            return local
        try:
            data = fetch(RAW_BASE + p, timeout=15, retries=1)
            with open(local, "wb") as f:
                f.write(data)
            return local
        except Exception as e:  # noqa: BLE001
            log(f"[!] 跳过 {p}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=24) as ex:
        files = [f for f in ex.map(one, paths) if f]
    log(f"[i] 从 GitHub 获取 {len(files)}/{len(paths)} 个频道清单")
    return files


def load_mappings(files):
    """xmltv_id -> [(site, site_id, lang, name)]"""
    by_id = defaultdict(list)
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except Exception:  # noqa: BLE001
            continue
        for ch in root.iter("channel"):
            xid = (ch.get("xmltv_id") or "").strip()
            site = (ch.get("site") or "").strip()
            sid = (ch.get("site_id") or "").strip()
            if not xid or not site or not sid:
                continue
            by_id[xid].append(
                {"site": site, "site_id": sid, "lang": (ch.get("lang") or "").strip(),
                 "name": (ch.text or "").strip()}
            )
    return by_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m3u", default="https://iptv-org.github.io/iptv/index.m3u")
    ap.add_argument("-o", "--out", default="build/channels.xml")
    ap.add_argument("--epg-repo", default="", help="本地 iptv-org/epg 仓库路径（可选，加速）")
    ap.add_argument("--cache", default=".cache/epg-lists")
    ap.add_argument("--max-per-channel", type=int, default=1,
                    help="每个频道最多保留几个抓取源（默认 1，越多越慢）")
    ap.add_argument("--group", default="", help="只保留 group-title 匹配该正则的频道")
    ap.add_argument("--id", dest="id_filter", default="", help="只保留 tvg-id 匹配该正则的频道")
    ap.add_argument("--report", default="", help="输出 JSON 统计报告路径")
    args = ap.parse_args()

    log(f"[i] 读取播放列表 {args.m3u}")
    channels = parse_m3u(read_text(args.m3u))
    if args.group:
        rx = re.compile(args.group, re.I)
        channels = [c for c in channels if rx.search(c["group"])]
    if args.id_filter:
        rx = re.compile(args.id_filter)
        channels = [c for c in channels if rx.search(c["id"])]
    log(f"[i] 频道数 {len(channels)}")

    by_id = load_mappings(epg_repo_files(args.epg_repo, args.cache))
    log(f"[i] 抓取源共覆盖 {len(by_id)} 个 xmltv_id")

    # 站点覆盖度，用于排序：覆盖越多的站点通常维护得越好
    site_cov = Counter()
    for rows in by_id.values():
        for s in {r["site"] for r in rows}:
            site_cov[s] += 1

    matched, unmatched = [], []
    for ch in channels:
        cid = ch["id"]
        cands, kind = [], None
        if cid and cid in by_id:
            cands, kind = by_id[cid], "exact"
        elif cid and "@" in cid and cid.split("@")[0] in by_id:
            cands, kind = by_id[cid.split("@")[0]], "suffix"
        if not cands:
            unmatched.append(ch)
            continue
        # 去重 + 排序：精确匹配优先，其次站点覆盖度高的，最后按站点名
        seen, uniq = set(), []
        for r in cands:
            key = (r["site"], r["site_id"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        uniq.sort(key=lambda r: (-site_cov[r["site"]], r["site"], r["site_id"]))
        for r in uniq[: max(1, args.max_per_channel)]:
            matched.append({"xmltv_id": cid, "name": ch["name"], "match": kind, **r})

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    tv = ET.Element("channels")
    seen_rows = set()
    for m in matched:
        key = (m["site"], m["xmltv_id"], m["site_id"])
        if key in seen_rows:
            continue
        seen_rows.add(key)
        el = ET.SubElement(tv, "channel", {
            "site": m["site"],
            "lang": m["lang"] or "en",
            "xmltv_id": m["xmltv_id"],
            "site_id": m["site_id"],
        })
        el.text = m["name"] or m["xmltv_id"]
    ET.indent(tv, space="  ")
    with open(args.out, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(ET.tostring(tv, encoding="utf-8"))

    covered_ids = {m["xmltv_id"] for m in matched}
    stats = {
        "playlist_channels": len(channels),
        "covered_channels": len(covered_ids),
        "coverage_pct": round(100 * len(covered_ids) / len(channels), 1) if channels else 0,
        "channel_entries": len(seen_rows),
        "sites": len({m["site"] for m in matched}),
        "top_sites": Counter(m["site"] for m in matched).most_common(15),
        "unmatched_sample": [c["id"] for c in unmatched[:20]],
    }
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)) or ".", exist_ok=True)
        json.dump(stats, open(args.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    log(f"[✓] 写入 {args.out}: {len(seen_rows)} 条抓取任务，"
        f"覆盖 {len(covered_ids)}/{len(channels)} 个频道 "
        f"({stats['coverage_pct']}%)，涉及 {stats['sites']} 个站点")
    print(json.dumps({k: stats[k] for k in ("playlist_channels", "covered_channels",
                                            "coverage_pct", "channel_entries", "sites")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
