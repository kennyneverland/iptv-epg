#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整理抓取器输出的 XMLTV：补齐频道信息、去重、排序、压缩。

用法:
    python3 postprocess.py build/guide.xml build/epg.xml --channels build/channels.xml --gzip
"""
import argparse
import gzip
import os
import sys
import xml.etree.ElementTree as ET


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--channels", default="", help="build_channels.py 生成的 channels.xml，用于补齐频道名")
    ap.add_argument("--gzip", action="store_true")
    ap.add_argument("--keep-past-days", type=int, default=1)
    args = ap.parse_args()

    if not os.path.exists(args.input):
        log(f"[!] 找不到 {args.input}，抓取可能全部失败")
        sys.exit(1)

    tree = ET.parse(args.input)
    tv = tree.getroot()

    names = {}
    if args.channels and os.path.exists(args.channels):
        for ch in ET.parse(args.channels).getroot().iter("channel"):
            names[ch.get("xmltv_id")] = (ch.text or "").strip()

    have = {c.get("id") for c in tv.findall("channel")}
    added = 0
    for cid, name in names.items():
        if cid and cid not in have:
            el = ET.SubElement(tv, "channel", {"id": cid})
            dn = ET.SubElement(el, "display-name")
            dn.text = name or cid
            added += 1

    # 去重
    seen, dup = set(), 0
    progs = []
    for p in tv.findall("programme"):
        title_el = p.find("title")
        title = (title_el.text or "") if title_el is not None else ""
        key = (p.get("channel"), p.get("start"), p.get("stop"), title)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        progs.append(p)

    for p in tv.findall("programme"):
        tv.remove(p)
    progs.sort(key=lambda p: (p.get("channel") or "", p.get("start") or ""))
    for p in progs:
        tv.append(p)

    ET.indent(tv, space="  ")
    raw = ET.tostring(tv, encoding="utf-8")
    body = b"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + raw
    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    with open(args.output, "wb") as f:
        f.write(body)

    out = args.output
    if args.gzip:
        out = args.output + ".gz"
        with gzip.open(out, "wb", compresslevel=9) as f:
            f.write(body)

    channels = len(tv.findall("channel"))
    log(f"[✓] {out}: {channels} 个频道 / {len(progs)} 条节目"
        f"（补齐频道 {added} 个，去重 {dup} 条，{os.path.getsize(out)/1024:.0f} KB）")
    print(f"{channels} channels, {len(progs)} programmes -> {out}")


if __name__ == "__main__":
    main()
