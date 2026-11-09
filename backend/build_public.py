#!/usr/bin/env python3
"""
build_public.py —— 建立「公開版」資料庫與可下載的場景骨架包

公開版與內網版是兩套東西：
  內網版  data/db.sqlite3     含絕對路徑、session id、私人記憶全文（只在 tailnet 內）
  公開版  data/public.sqlite3 只含可公開的內容：場景功用、技能名、層級架構、導讀文章

下載包：每個場景產生一個 zip，內容是「一個場景該有的骨架」——
        定位卡 / AGENTS.md 憲法 / 場景私有記憶.md / 場景畫像.md / 身份卡.md /
        _檔案索引.md / 專案記憶/ / 歸檔/
        （不含任何 .git、任何本機路徑、任何 session id）
"""
import json, os, re, sqlite3, zipfile, shutil, argparse, datetime, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser("~/services/scene-memory-backend")
SCENES_ROOT = os.path.expanduser("~/.DSH/工作台/場景")
SCENARIOS = os.path.expanduser("~/.DSH/工作台/外殼/scenarios")
PUBLIC_DB = os.path.join(ROOT, "data", "public.sqlite3")
DL_DIR = os.path.join(ROOT, "public", "downloads")
READING_DIR = os.path.join(ROOT, "content", "reading")

LAYERS = [
    (0, "L0", "全域憲法",
     "跨場景鐵律：記憶在檔案裡、場景主權、一次派單＝一條回執、有可觀察落點才算做完",
     "只有機主",
     "每輪對話自動注入，所以必須極短。不讀就會白幹的才放這裡。",
     "規定所有場景都得守的規矩",
     "往下定調：每一層的行為都從這裡的鐵律來"),
    (1, "L1", "共享層",
     "身份索引、跨場景看板、待辦板、衝突簿、路由表、工作流",
     "分區寫，各 owner 只寫自己的",
     "不屬於某個場景，誰需要誰讀。更新頻率最高的看板不該擠掉其他板。",
     "所有場景共用的台帳與路由",
     "往下承接：場景之間的協作在這裡發生"),
    (2, "L2", "場景私有層",
     "場景私有記憶.md（§〇 交接）／定位卡／身份卡／場景畫像／專案記憶／歸檔／場景專屬技能",
     "只有本場景",
     "唯一真源。換會話時它是唯一的入口。",
     "每個場景自己的記憶與專屬技能",
     "往下落地：由工具執行、寫入稽核"),
    (3, "L3", "執行與工具層",
     "引擎、工具腳本（校驗／建會話／發訊息／派單）、技能目錄",
     "由專人維護",
     "工具放在資料之外，升級不破壞資料。",
     "讓規矩真的被執行的那一層",
     "往下留痕：所有動作都寫進稽核層"),
    (4, "L4", "稽核層",
     "每個場景各自的 git 倉庫（git log 全在）、寫入審計日誌",
     "工具自動寫",
     "記憶變成有版本控制的資產，不是模型的體體記憶。",
     "誰改了什麼、何時改的，全在這裡",
     "往下封存：過去的版本進歸檔層"),
    (5, "L5", "歸檔層",
     "交接前快照、舊版記憶、歷史文稿",
     "只進不改",
     "任何東西都能回滾。歷史不能丟，也不能占著入口。",
     "過去的版本，只進不改",
     None),
]



def read(p, limit=None):
    try:
        t = open(p, encoding="utf-8", errors="replace").read()
        return t if limit is None else t[:limit]
    except Exception:
        return ""


def scene_purpose(desc):
    """從場景 json 的 description 抽出「功用」一句話（第一句）"""
    d = re.sub(r"^\s*[^:：]{1,20}[:：]\s*", "", (desc or "").strip())
    d = d.split("★")[0].strip()
    m = re.split(r"(?<=。)\s*", d)
    first = (m[0] if m else d).strip().rstrip("。")
    return first[:120] or "（未寫職責）"


def scene_boundary(desc):
    d = (desc or "").strip()
    m = re.search(r"(不碰[^\n。]*|不做[^\n。]*|不產[^\n。]*|不事[^\n。]*)", d)
    return (m.group(1).strip() if m else "")[:200]


def load_scenarios():
    out = {}
    if not os.path.isdir(SCENARIOS):
        return out
    for f in sorted(os.listdir(SCENARIOS)):
        if not f.endswith(".json") or f.startswith("_"):
            continue
        try:
            j = json.load(open(os.path.join(SCENARIOS, f), encoding="utf-8"))
        except Exception:
            continue
        if not j.get("id"):
            continue
        out[j["id"]] = j
    return out


def make_downloads(scenes_meta):
    """每個場景產生一個 zip 骨架包"""
    os.makedirs(DL_DIR, exist_ok=True)
    for old in os.listdir(DL_DIR):
        if old.endswith(".zip"):
            os.remove(os.path.join(DL_DIR, old))

    made = {}
    for sid, m in scenes_meta.items():
        name = m["name"]
        stage = os.path.join(ROOT, ".tmp-dl", name)
        if os.path.exists(stage):
            shutil.rmtree(stage)
        os.makedirs(os.path.join(stage, "專案記憶"), exist_ok=True)
        os.makedirs(os.path.join(stage, "歸檔"), exist_ok=True)
        os.makedirs(os.path.join(stage, ".dsh", "skills", sid), exist_ok=True)
        boundary_line = ("**邊界**：" + m["boundary"]) if m["boundary"] else ""

        # 定位卡（乾淨、沒有本機路徑）
        write(os.path.join(stage, "定位卡.md"), f"""# {name} · 定位卡

- 場景 id：`{sid}`
- 場景名：{name}
- 面板：`scenarios/{sid}.json`
- 記憶目錄：`場景/{name}/`
- 專屬技能：`{sid}`（`場景/{name}/.dsh/skills/{sid}/SKILL.md`）
- 定位卡版本：1
""")

        # AGENTS.md 憲法
        write(os.path.join(stage, "AGENTS.md"), f"""# 場景憲法 · {name}（`{sid}`）

## 職責
{m['purpose']}
{('邊界：' + m['boundary']) if m['boundary'] else ''}

## 邊界
- 不寫別的場景的記憶（發現寫錯 → 派單或留言提醒，⛔ 不許代改）
- 不刪檔、不代改別的場景的記憶

## 歸屬檢查（動手前必做）
1. 先判這活歸誰：`node <工作台>/工具/派單.mjs 路由 --要 "<一句話>"`
   - 命中 → 那是正主，本場景只做自己那份，其餘派單給它
   - 退出碼 3 → 讀該場景 `AGENTS.md` 的職責段；仍不確定 → 問使用者
2. 本場景職責外的活，一律派單，不得自己動手。

## 記憶規則
- 記憶真源：`場景私有記憶.md` 的 `## §〇 當前交接`（≤4 KB，覆蓋寫）
- 只寫自己的記憶。⛔ 不許代改別的場景。
- 詳細決策追加進 `## §五 決策與坑`（只追加，不改寫）。

## 換會話
1. 先寫 §〇 交接
2. 跑 `node <工作台>/工具/場景記憶.mjs check --場景 {name}`
3. 不過不許換。換完同步三處（場景 json 的 sessionId／身份索引表／§〇 署名）

## 跨場景
- 一次派單 = 一條回執。「活干完了但对方还不知道」＝没干完。
- 有可見落點（檔案／日誌／狀態字）才算做完。
""")

        # 場景私有記憶.md 骨架
        write(os.path.join(stage, "場景私有記憶.md"), f"""## §〇 當前交接（≤4 KB，新會話先讀這一節）

### 1) 上次交接
- （第一次：寫下這次場景為什麼被開出來）

### 2) 當前專案
| 專案 | 記憶檔 | 狀態 | 下一步 |
|---|---|---|---|
| （暫無） | — | — | — |

### 3) 私有記憶變更
- （本輪改了什麼，≤3 行）

### 4) 下一步 / 卡點
- 下一步：<誰先動，按什麼順序>
- 卡點：無

### 5) 全貌
- 專案記憶 0 個 · 歸檔 0 份 · 索引 _檔案索引.md
- 身份卡 / 場景畫像 已就位
- 卡點 / 等誰：見第 4 節

## 核心職責

- 負責：{m['purpose']}
- 不碰：別的場景的記憶目錄。發現別人寫錯 ⇒ 只能發請求，不許代改。
- 一句话：{m['purpose']}

## §一 我管什麼 / 不管什麼

- 管：{m['purpose']}
- 不管：任何真實工作。

## §二 幹活入口

- 專屬技能：`.dsh/skills/{sid}/SKILL.md`
- 場景 json：`外殼/scenarios/{sid}.json`
- 身份索引：`場景/_場景身份索引.md`

## §五 決策與坑（只追加）

- （決策寫這裡；坑寫這裡；下一任才看得到）
""")

        # 身份卡 / 場景畫像（工具生成，這裡給佔位說明）
        write(os.path.join(stage, "身份卡.md"), f"""# {name} · 身份卡（工具生成 · ⛔ 手改即校验失败）

<!-- 場景绑定 BEGIN · 由 場景記憶.mjs 生成，⛔ 手改即校验失败 -->
> **場景** `{sid}` ｜ **面板** `（尚未綁定）` ｜ **會話** `（尚未綁定）`
> **定位卡** `場景/{name}/定位卡.md` ｜ **卡指纹** `sha256:（尚未蓋章）…` ｜ **盖章** （尚未蓋章）
> **地盘** `場景/{name}/`
> **權限** 只写自己的记忆文件夹与本人资产；⛔ 不改别的場景、不重启引擎
> **专属技能** {sid}
<!-- 場景绑定 END -->

## 怎麼用
- 這個檔由 `場景記憶.mjs stamp --場景 {name}` 全量產生。
- 要補說明請寫進 `場景私有記憶.md`，別寫這裡。
""")
        write(os.path.join(stage, "場景畫像.md"), f"""# {name} · 場景畫像（工具生成 · 由場景 json 推導）

> 來源：`scenarios/{sid}.json` ｜ 這個檔由 `場景記憶.mjs stamp` 產生。
> 一句话：{m['purpose']}

## 一、形態
- 布局 grid ｜ 面板數：見場景 json

## 二、專屬技能
- {sid}

## 三、記憶
- 記憶資料夾：`場景/{name}/`
- 交接段：`場景私有記憶.md` 的 §〇（≤ 4 KB）
- 專案記憶：`專案記憶/`（≤ 8 KB／份）

## 四、依賴與入口
- 定位卡：`場景/{name}/定位卡.md`
- 記憶真源：`場景/{name}/場景私有記憶.md`
""")

        write(os.path.join(stage, "_檔案索引.md"), f"""# {name} · 檔案索引

> 状态四态：`活 / 常備 / 留档 / 待清`

| 文件 / 目錄 | 是什么 | 状态 | 复核日期 |
|---|---|---|---|
| `場景私有記憶.md` | 場景私有記憶（人写：交接/职责/决策/项目索引） | 活 | |
| `身份卡.md` | 身份卡（工具生成：身份/權限/定位卡指纹） | 活 | |
| `場景畫像.md` | 場景畫像（工具生成：布局/面板/渲染器） | 活 | |
| `專案記憶\\` | 每个项目一份记忆 | 活 | |
| `歸檔\\` | 旧版本快照（只进不改） | 留档 | |
""")

        write(os.path.join(stage, ".dsh", "skills", sid, "SKILL.md"), f"""---
name: {sid}
description: {m['purpose']}
---

# {sid}

> 這個場景專屬的技能：只有 `{name}` 場景看得到。
> 別的場景連清單裡都不會有它。

## 做法

（把這場景特有的做法寫在這裡。references/ 放較長的參考資料，
scripts/ 放可執行的腳本。單篇上限 12 KB，超了拆主檔＋子檔。）
""")

        write(os.path.join(stage, "README.md"), f"""# {name} — 場景骨架

這是「Gary 的場景記憶架構」裡 `{name}` 場景的可下載骨架。

**功用**：{m['purpose']}
{boundary_line}

## 怎麼用

```
1. git init                     ← 這是場景邊界，沒有它引擎不會載入這個場景的技能
2. 複製這個資料夾成 場景/{name}/
3. 寫 §〇 交接（我是誰／幹到哪／下一步／卡在哪）
4. 跑 node <工作台>/工具/場景記憶.mjs stamp --場景 {name}   ← 產生身份卡與場景畫像
5. 跑 node <工作台>/工具/場景記憶.mjs check --場景 {name}   ← 全綠才算完成
```

## 裡面有什麼

| 檔案 | 誰寫 | 作用 |
|---|---|---|
| `定位卡.md` | 人 | 身分的真源（靜態）。sha256 會成為身份卡裡的「卡指紋」 |
| `AGENTS.md` | 人 | 場景憲法：職責、邊界、歸屬檢查、記憶規則、換會話流程 |
| `場景私有記憶.md` | 人 | **記憶真源**：§〇 交接（≤4 KB，覆蓋寫）＋§五 決策與坑（只追加） |
| `身份卡.md` | 工具 | 現況快照（場景／面板／會話 id、卡指紋、地盤、權限）。⛔ 手改即校驗失敗 |
| `場景畫像.md` | 工具 | 面板視圖（布局、座標、渲染器）。由場景 json 推導 |
| `.dsh/skills/{sid}/` | 人 | 場景專屬技能。只有這個場景看得到 |
| `專案記憶/` | 人 | 一專案一份，≤8 KB |
| `歸檔/` | 人 | 交接前快照，只進不改 |
| `_檔案索引.md` | 人 | 檔案清冊：狀態四態 ＋複核日期 |

> 這個包**不含** `.git/`（你自己 `git init`）、不含任何本機路徑、不含任何 session id。
""")

        zip_name = f"{sid}.zip"
        with zipfile.ZipFile(os.path.join(DL_DIR, zip_name), "w", zipfile.ZIP_DEFLATED) as z:
            for dirpath, _, files in os.walk(stage):
                for fn in sorted(files):
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, stage)
                    z.write(full, os.path.join(name, rel))
        made[sid] = zip_name

    tmp = os.path.join(ROOT, ".tmp-dl")
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    return made


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)


def build():
    scen = load_scenarios()
    # 場景目錄 → id 對應（用 場景/<名>/ 的主技能或定位卡）
    by_name = {}
    for sid, j in scen.items():
        by_name[j.get("name", sid)] = (sid, j)

    scenes_meta = {}
    if os.path.isdir(SCENES_ROOT):
        for name in sorted(os.listdir(SCENES_ROOT)):
            sdir = os.path.join(SCENES_ROOT, name)
            if not os.path.isdir(sdir) or name.startswith("_"):
                continue
            card = read(os.path.join(sdir, "定位卡.md"))
            m = re.search(r"場景 id：`([^`]+)`", card)
            sid = m.group(1) if m else None
            if not sid:
                j = by_name.get(name)
                sid = j[0] if j else None
            if not sid:
                continue
            desc = (scen.get(sid) or {}).get("description", "")
            if not desc:
                desc = read(os.path.join(sdir, "AGENTS.md"))[:400]
            skills = []
            sk = os.path.join(sdir, ".dsh", "skills")
            if os.path.isdir(sk):
                skills = sorted(d for d in os.listdir(sk)
                                if os.path.isfile(os.path.join(sk, d, "SKILL.md")))
            nfiles = sum(1 for f in ("AGENTS.md", "定位卡.md", "身份卡.md", "場景畫像.md",
                                     "場景私有記憶.md", "專案記憶", "歸檔", "_檔案索引.md")
                         if os.path.exists(os.path.join(sdir, f)))
            panels = (scen.get(sid) or {}).get("panels", [])
            scenes_meta[sid] = {
                "name": name,
                "purpose": scene_purpose(desc),
                "detail": desc.strip(),
                "boundary": scene_boundary(desc),
                "skills": skills,
                "nfiles": nfiles,
                "npanels": len(panels),
                "panels": panels,
            }

    downloads = make_downloads(scenes_meta)

    con = sqlite3.connect(PUBLIC_DB)
    con.executescript(open(os.path.join(HERE, "schema_public.sql"), encoding="utf-8").read())
    cur = con.cursor()
    now = datetime.datetime.now().isoformat(timespec="seconds")

    for sid, m in scenes_meta.items():
        cur.execute("INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?)",
                    (sid, m["name"], m["purpose"], m["detail"], m["boundary"],
                     len(m["skills"]), m["nfiles"], m["npanels"], downloads.get(sid)))
        for s in m["skills"]:
            cur.execute("INSERT OR IGNORE INTO scene_skills VALUES (?,?)", (sid, s))
        for p in m["panels"]:
            cur.execute("INSERT OR IGNORE INTO scene_panels VALUES (?,?,?,?)",
                        (sid, p.get("id"), p.get("title"), p.get("type")))

    for L in LAYERS:
        cur.execute("INSERT INTO layers VALUES (?,?,?,?,?,?,?,?)", L)

    # 導讀：讀 content/reading/*.md（使用者自撰）
    READING_DIR_SEQ = [
        ("01-what-is-this", "這是什麼"),
        ("02-why-scenes", "為什麼需要場景"),
        ("03-three-layers", "記憶的三層"),
        ("04-boundaries", "邊界怎麼劃"),
        ("05-handover", "§〇 交接怎麼寫"),
        ("06-dispatch", "派單與回執"),
        ("07-accumulable", "可累積物"),
        ("08-sovereignty", "場景主權"),
        ("09-single-source", "單一權威"),
        ("10-workflow", "工作流"),
        ("11-scene-vs-subagent", "場景 vs 臨時執行體"),
        ("12-ledger-vs-wiki", "帳本 vs wiki"),
    ]
    for i, (slug, title) in enumerate(READING_DIR_SEQ, 1):
        f = os.path.join(READING_DIR, slug + ".md")
        body = read(f) if os.path.exists(f) else ""
        status = "published" if body.strip() else "draft"
        cur.execute("INSERT INTO reading VALUES (?,?,?,?,?)", (slug, i, title, status, body))

    for k, v in {"built_at": now, "scene_count": str(len(scenes_meta)),
                 "reading_count": str(len(READING_DIR_SEQ)), "schema_version": "1"}.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))

    con.commit()
    stats = dict(
        scenes=cur.execute("SELECT COUNT(*) FROM scenes").fetchone()[0],
        layers=cur.execute("SELECT COUNT(*) FROM layers").fetchone()[0],
        reading=cur.execute("SELECT COUNT(*) FROM reading").fetchone()[0],
        published=cur.execute("SELECT COUNT(*) FROM reading WHERE status='published'").fetchone()[0],
        downloads=len(downloads),
    )
    con.close()
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.parse_args()
    st = build()
    for k, v in st.items():
        print(f"{k}: {v}")
    print("db:", PUBLIC_DB, os.path.getsize(PUBLIC_DB), "bytes")
    print("downloads:", DL_DIR)
