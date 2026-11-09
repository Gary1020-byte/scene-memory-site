#!/usr/bin/env python3
"""
build_static.py —— 把公開版站台編成**純靜態** dist/

為什麼需要：任何託管商（GitHub Pages / Cloudflare Pages / Netlify / Vercel）
都只吃靜態檔。原網站靠 fetch('/api/...') 取資料，必須在建置時固化。

做法：
  1. 從 data/public.sqlite3 匯出 data/{scenes,layers,reading}.json
  2. site/ → dist/，把 BASE 前綴寫死（GitHub Pages 是子路徑）
  3. 多頁路由展開成真實目錄（/scenes → dist/scenes/index.html）
  4. 導讀每篇展開成 dist/reading/<slug>/index.html
  5. 下載包複製到 dist/downloads/

用法：
  python3 backend/build_static.py --base /scene-memory-architecture
  python3 backend/build_static.py --base ""            # 根網域
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DL = ROOT / "public" / "downloads"
DB = ROOT / "data" / "public.sqlite3"
DIST = ROOT / "dist"

# 路由：URL 前綴 → 對應的 html 檔
ROUTES = {
    "/": "index.html",
    "/architecture": "architecture.html",
    "/scenes": "scenes.html",
    "/reading": "reading.html",
    "/start": "start.html",
}


def dump_data(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    scenes = []
    for s in db.execute("SELECT * FROM scenes ORDER BY name"):
        d = dict(s)
        d["skills"] = [r["name"] for r in db.execute(
            "SELECT name FROM scene_skills WHERE scene=? ORDER BY name", (s["id"],))]
        d["panels"] = [dict(r) for r in db.execute(
            "SELECT id,title,type FROM scene_panels WHERE scene=?", (s["id"],))]
        d["download_url"] = f"/downloads/{s['download']}" if s["download"] else None
        scenes.append(d)

    layers = [dict(r) for r in db.execute("SELECT * FROM layers ORDER BY id")]
    reading = [dict(r) for r in db.execute(
        "SELECT slug,seq,title,status,body FROM reading ORDER BY seq")]

    meta = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM meta")}

    for name, payload in (("scenes", {"scenes": scenes}),
                          ("layers", {"layers": layers}),
                          ("reading", {"reading": reading}),
                          ("meta", {"meta": meta})):
        (dest / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    db.close()
    return len(scenes), len(layers), len(reading)


def rewrite(text: str, base: str) -> str:
    """把絕對路徑改成帶 BASE 前綴；並留一個 base 供 runtime 兜底。"""
    text = text.replace('href="/assets/', f'href="{base}/assets/')
    text = text.replace('src="/assets/', f'src="{base}/assets/')
    # runtime 反推 BASE 的 fallback：注入 data-base
    if "<head>" in text:
        text = text.replace(
            "<head>",
            f'<head>\n<meta name="base-path" content="{base}">', 1)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="", help="部署子路徑，例：/scene-memory-architecture；根網域留空")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    n_scenes, n_layers, n_reading = dump_data(DIST / "data")

    # assets
    shutil.copytree(SITE / "assets", DIST / "assets")

    # 靜態 html（來源頁）
    for f in SITE.glob("*.html"):
        html = rewrite(f.read_text(encoding="utf-8"), base)
        (DIST / f.name).write_text(html, encoding="utf-8")

    # 多頁路由 → 目錄 index.html
    for url, fname in ROUTES.items():
        if url == "/":
            continue
        d = DIST / url.lstrip("/")
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DIST / fname, d / "index.html")

    # 導讀每篇 → reading/<slug>/index.html
    reading = json.loads((DIST / "data" / "reading.json").read_text(encoding="utf-8"))["reading"]
    for r in reading:
        d = DIST / "reading" / r["slug"]
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DIST / "reading-article.html", d / "index.html")

    # 下載包
    if DL.exists():
        shutil.copytree(DL, DIST / "downloads")

    # 404 → 首頁
    shutil.copy2(DIST / "index.html", DIST / "404.html")

    total = sum(1 for _ in DIST.rglob("*") if _.is_file())
    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"dist/ 建好：{total} 檔 · {size/1024:.0f} KB · base={base or '(root)'}")
    print(f"  {n_scenes} 場景 · {n_layers} 層 · {n_reading} 導讀 · "
          f"{len(list((DIST/'downloads').glob('*.zip'))) if (DIST/'downloads').exists() else 0} 下載包")


if __name__ == "__main__":
    main()
