#!/usr/bin/env python3
"""
build_db.py —— 場景記憶架構後端資料庫建構器

把兩種來源灌進同一個 SQLite：
  ① 機器現況（scenes/*）      —— 掃 ~/.DSH/工作台/場景
  ② 知識頁（concepts/*）      —— 讀 LLM-Wiki 的 13 頁 wikilink 知識庫
再用 edges 表把兩者連起來。

用法：
  python3 backend/build_db.py            # 建庫
  python3 backend/build_db.py --json     # 同時輸出 db.json（給靜態前端 fallback）
"""
import json, os, re, sqlite3, subprocess, hashlib, argparse, datetime

ROOT = os.path.expanduser("~/.DSH/工作台/場景")
WIKI = os.path.expanduser("~/services/shared-vault/LLM-Wiki")
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "data", "db.sqlite3")
JSON_OUT = os.path.join(HERE, "..", "data", "db.json")

# 13 頁知識庫（建立順序＝閱讀順序）
CONCEPT_SLUGS = [
    ("scene-memory-architecture-overview", "overview"),
    ("scene-memory-architecture", "entity"),
    ("scene-as-accumulation-carrier", "concept"),
    ("git-as-boundary-and-routing", "concept"),
    ("three-layer-memory", "concept"),
    ("handover-section-zero", "concept"),
    ("scene-sovereignty", "concept"),
    ("dispatch-and-receipt", "concept"),
    ("accumulable-artifact", "concept"),
    ("single-source-of-truth-rule", "concept"),
    ("workflow-as-scene-orchestration", "concept"),
    ("scene-vs-ephemeral-subagent", "comparison"),
    ("ledger-vs-wiki-memory", "comparison"),
]

ITEM_META = {
    "AGENTS.md":        {"role": "場景憲法", "layer": "注入層",
        "desc": "本場景的行為守則：職責、邊界、歸屬檢查、記憶規則、換會話流程。每輪注入給本場景會話。"},
    "定位卡.md":        {"role": "身分真源", "layer": "注入層",
        "desc": "靜態登記：場景 id、名稱、面板、記憶目錄、專屬技能。內容的 sha256 會成為身份卡裡的「卡指紋」。"},
    "身份卡.md":        {"role": "現況快照", "layer": "注入層",
        "desc": "工具生成：此刻的場景／面板／會話 id、定位卡指紋、地盤、權限、專屬技能。手改即校驗失敗。"},
    "場景畫像.md":      {"role": "面板視圖", "layer": "注入層",
        "desc": "工具生成：從 scenarios/<id>.json 推導的布局、面板座標、渲染器、依賴。"},
    "場景私有記憶.md":  {"role": "記憶真源", "layer": "注入層",
        "desc": "唯一真源。§〇 當前交接（≤4 KB，覆蓋寫）＋§五 決策與坑（只追加）。開場第一份讀。"},
    "專案記憶/":        {"role": "專案層", "layer": "注入層",
        "desc": "一專案一份 .md，≤8 KB：狀態／一句話／成果證據／下一步／坑。"},
    "歸檔/":            {"role": "快照倉庫", "layer": "注入層",
        "desc": "交接前的舊版快照。只進不改，可回滾。"},
    "_檔案索引.md":     {"role": "檔案清冊", "layer": "注入層",
        "desc": "場景內檔案的清冊：狀態（活／常備／留檔／待清）＋複核日期。"},
}

# ───────────── helpers ─────────────
def read(p, limit=None):
    try:
        t = open(p, encoding="utf-8", errors="replace").read()
        return t if limit is None else t[:limit]
    except Exception:
        return ""

def size(p):
    try: return os.path.getsize(p)
    except Exception: return 0

def sha8(p):
    try:
        with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception: return None

def first_desc(t):
    m = re.search(r"^description:\s*(.+)$", t, re.M)
    if m: return m.group(1).strip().strip('"')
    for line in t.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("---"):
            return s[:120]
    return ""

def section0(text):
    m = re.search(r"##\s*§〇[^\n]*\n(.*?)(?=\n##\s|\Z)", text, re.S)
    return m.group(1).strip() if m else ""

def skills_of(sdir):
    base = os.path.join(sdir, ".dsh", "skills")
    out = []
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            sp = os.path.join(base, name, "SKILL.md")
            if os.path.isfile(sp):
                out.append({"name": name, "size": size(sp), "desc": first_desc(read(sp, 4000))})
    return out

def split_blocks(md):
    """把 markdown 切成 (heading, level, body) 區塊"""
    blocks, cur_h, cur_lv, buf = [], None, 0, []
    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if cur_h is not None:
                blocks.append((cur_h, cur_lv, "\n".join(buf).strip()))
            cur_h, cur_lv, buf = m.group(2).strip(), len(m.group(1)), []
        else:
            buf.append(line)
    if cur_h is not None:
        blocks.append((cur_h, cur_lv, "\n".join(buf).strip()))
    return blocks

def fm(md):
    """抓 frontmatter 的 title/summary/tags"""
    title, tags = "", ""
    m = re.match(r"^---\n(.*?)\n---", md, re.S)
    summary = ""
    if m:
        fm_text = m.group(1)
        t = re.search(r"^title:\s*(.+)$", fm_text, re.M)
        if t: title = t.group(1).strip().strip('"')
        tg = re.search(r"^tags:\s*\[(.*?)\]", fm_text, re.M)
        if tg: tags = tg.group(1).strip()
        body = md[m.end():]
    else:
        body = md
    h = re.search(r"^#\s+(.+)$", body, re.M)
    if h and not title: title = h.group(1).strip()
    lines = [l.strip() for l in body.splitlines()]
    for l in lines:
        if l and not l.startswith("#") and not l.startswith(">") and not l.startswith("---") and not l.startswith("|"):
            summary = l[:300]; break
    return title, tags, summary, body

# ───────────── build ─────────────
def build():
    con = sqlite3.connect(os.path.abspath(DB))
    con.executescript(open(os.path.join(HERE, "schema.sql"), encoding="utf-8").read())
    now = datetime.datetime.now().isoformat(timespec="seconds")
    cur = con.cursor()

    # ① 場景
    scene_names = []
    for name in sorted(os.listdir(ROOT)):
        sdir = os.path.join(ROOT, name)
        if not os.path.isdir(sdir) or name.startswith("_"):
            continue
        scene_names.append(name)
        sid = name
        mem = read(os.path.join(sdir, "場景私有記憶.md"))
        s0 = section0(mem)
        sk = skills_of(sdir)
        nfiles = sum(1 for fn in ITEM_META if os.path.exists(os.path.join(sdir, fn)))
        cur.execute(
            "INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, name, sdir, int(os.path.isdir(os.path.join(sdir, ".git"))),
             len(s0.encode("utf-8")), s0, len(sk), nfiles, now))
        for fn, meta in ITEM_META.items():
            p = os.path.join(sdir, fn)
            if os.path.isdir(p):
                kids = sorted(os.listdir(p))
                cur.execute("INSERT INTO scene_files (scene,name,kind,role,layer,desc,size,sha,count,content) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sid, fn, "dir", meta["role"], meta["layer"], meta["desc"],
                     sum(size(os.path.join(p, k)) for k in kids if os.path.isfile(os.path.join(p, k))),
                     None, len(kids), None))
            elif os.path.isfile(p):
                body = read(p)
                cur.execute("INSERT INTO scene_files (scene,name,kind,role,layer,desc,size,sha,count,content) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sid, fn, "file", meta["role"], meta["layer"], meta["desc"],
                     size(p), sha8(p), None, body))
            else:
                cur.execute("INSERT INTO scene_files (scene,name,kind,role,layer,desc,size,sha,count,content) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (sid, fn, "missing", meta["role"], meta["layer"], meta["desc"], 0, None, None, None))
        for s in sk:
            cur.execute("INSERT INTO scene_skills VALUES (?,?,?,?)", (sid, s["name"], s["size"], s["desc"]))
        portrait = read(os.path.join(sdir, "場景畫像.md"))
        for pid, title, ptype in re.findall(r"\|\s*`?([a-z0-9-]+)`?\s*\|\s*([^|]+?)\s*\|\s*`?([a-z-]+)`?\s*\|", portrait):
            cur.execute("INSERT OR IGNORE INTO scene_panels VALUES (?,?,?,?)", (sid, pid, title.strip(), ptype))

    # ② 共享層
    sdir = os.path.join(ROOT, "_共享記憶")
    if os.path.isdir(sdir):
        for fn in sorted(os.listdir(sdir)):
            p = os.path.join(sdir, fn)
            if os.path.isfile(p):
                cur.execute("INSERT INTO shared_files VALUES (?,?,?)", (fn, size(p), read(p)))

    # ③ 概念頁
    slug_set = set()
    for i, (slug, ctype) in enumerate(CONCEPT_SLUGS):
        path = None
        for d in ("overviews", "entities", "concepts", "comparisons", "summaries"):
            cand = os.path.join(WIKI, "wiki", d, slug + ".md")
            if os.path.isfile(cand):
                path = cand; break
        if not path:
            print("  ! 找不到概念頁", slug); continue
        md = read(path)
        title, tags, summary, body = fm(md)
        slug_set.add(slug)
        cur.execute("INSERT INTO concepts VALUES (?,?,?,?,?,?,?,?)",
            (slug, title or slug, ctype, path, summary, tags, body, i))
        for j, (h, lv, b) in enumerate(split_blocks(body)):
            cur.execute("INSERT INTO concept_blocks VALUES (?,?,?,?,?)", (slug, j, h, lv, b))
        # ④ edges：概念 → 概念
        for m in re.findall(r"\[\[([^\]\|]+)", body):
            tgt = m.strip()
            if tgt in slug_set and tgt != slug:
                cur.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?)", (slug, tgt, "concept->concept", None))
        # 概念 → 場景（正文提到場景名）
        for sn in scene_names:
            if sn in body:
                cur.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?)", (slug, sn, "concept->scene", None))

    # meta
    for k, v in {
        "built_at": now,
        "scene_root": ROOT,
        "wiki_root": WIKI,
        "scene_count": str(len(scene_names)),
        "concept_count": str(len(slug_set)),
        "schema_version": "1",
    }.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))

    con.commit()

    stats = dict(
        scenes=cur.execute("SELECT COUNT(*) FROM scenes").fetchone()[0],
        scene_files=cur.execute("SELECT COUNT(*) FROM scene_files").fetchone()[0],
        skills=cur.execute("SELECT COUNT(*) FROM scene_skills").fetchone()[0],
        panels=cur.execute("SELECT COUNT(*) FROM scene_panels").fetchone()[0],
        shared=cur.execute("SELECT COUNT(*) FROM shared_files").fetchone()[0],
        concepts=cur.execute("SELECT COUNT(*) FROM concepts").fetchone()[0],
        blocks=cur.execute("SELECT COUNT(*) FROM concept_blocks").fetchone()[0],
        edges=cur.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
        missing_git=[r[0] for r in cur.execute("SELECT name FROM scenes WHERE has_git=0")],
        handover_over=[(r[0], r[1]) for r in cur.execute("SELECT name, handover_size FROM scenes WHERE handover_size>4096")],
    )
    con.close()
    return stats

def dump_json():
    con = sqlite3.connect(os.path.abspath(DB)); con.row_factory = sqlite3.Row
    d = {
        "meta": {r[0]: r[1] for r in con.execute("SELECT key, value FROM meta")},
        "scenes": [],
        "shared": [],
        "concepts": [],
        "edges": [dict(r) for r in con.execute("SELECT * FROM edges")],
    }
    for r in con.execute("SELECT * FROM scenes ORDER BY name"):
        s = dict(r); s.pop("handover_b64", None)
        s["files"] = [dict(x) for x in con.execute("SELECT * FROM scene_files WHERE scene=?", (s["id"],))]
        s["skills"] = [dict(x) for x in con.execute("SELECT * FROM scene_skills WHERE scene=?", (s["id"],))]
        s["panels"] = [dict(x) for x in con.execute("SELECT * FROM scene_panels WHERE scene=?", (s["id"],))]
        d["scenes"].append(s)
    for r in con.execute("SELECT * FROM shared_files"):
        x = dict(r); x["content"] = x["content"][:4000]; d["shared"].append(x)
    for r in con.execute("SELECT * FROM concepts ORDER BY order_no"):
        c = dict(r); c.pop("body", None)
        c["blocks"] = [dict(x) for x in con.execute("SELECT * FROM concept_blocks WHERE slug=?", (c["slug"],))]
        d["concepts"].append(c)
    con.close()
    json.dump(d, open(JSON_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    st = build()
    if a.json: dump_json()
    for k, v in st.items(): print(f"{k}: {v}")
    print("db:", os.path.abspath(DB), size(os.path.abspath(DB)), "bytes")
    if a.json: print("json:", os.path.abspath(JSON_OUT), size(os.path.abspath(JSON_OUT)), "bytes")
