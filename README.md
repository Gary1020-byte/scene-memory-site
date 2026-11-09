# scene-memory-backend —— 場景記憶架構的專門資料庫（網頁後端）

## ⚠️ 兩套後端，分開的

| | 內網版 | **公開版**（要發布到網路上的） |
|---|---|---|
| 服務 | `backend/server.mjs` :8787 | `backend/server_public.mjs` :8788 |
| 資料庫 | `data/db.sqlite3` | `data/public.sqlite3` |
| 網址 | `/scene-memory/` | `/scene-memory-public/` |
| 內容 | 絕對路徑、session id、**場景私有記憶全文**、共享層全文 | **只有可公開內容**：場景功用、技能名、六層架構、導讀文章 |
| 用途 | 你的工作台觀測站 | 給外面的人看、給人下載骨架 |

**公開版不提供任何會洩漏本機狀態的端點。** 下載包也已掃過：不含 `.git/`、不含本機路徑、不含 session id。

### 公開版怎麼更新

```bash
bash scripts/refresh_public.sh
```

重建公開庫 → 重啟服務 → 印筆數。

### 導讀文章怎麼發布

寫在 `content/reading/<slug>.md`，然後跑上面的 refresh。
**有內容＝已發布；空白＝「待撰寫」**（網站顯示佔位）。

檔名對應表見 `content/reading/README.md`。

## 下載包

`public/downloads/<scene-id>.zip` — 每個場景一份骨架（8 個檔案）：
定位卡 / AGENTS.md 憲法 / 場景私有記憶.md / 身份卡.md / 場景畫像.md /
_檔案索引.md / .dsh/skills/<id>/SKILL.md / README.md（怎麼用）。

由 `backend/build_public.py` 產生，**每次重建都重新生成**。

> 這是**獨立的後端**：把「機器現況」與「架構知識」灌進同一個 SQLite，
> 用 REST API 出給前端。原始的互動設計圖把整包 JSON 內嵌進 HTML（616 KB 單檔），
> 資料一更新就要重跑 build；改成後端之後，前端只 fetch，資料更新只重跑建庫。

## 兩種資料來源

| | 來源 | 內容 |
|---|---|---|
| **機器現況** | `~/.DSH/工作台/場景/` | 24 個場景 × 8 個記憶檔（含全文）、148 個專屬技能、32 個面板、共享層 12 檔 |
| **架構知識** | `~/services/shared-vault/LLM-Wiki/` | 13 頁 wikilink 知識庫（overview / entity / 9 concepts / 2 comparisons） |

兩者用 `edges` 表連起來：**概念頁 → 概念頁**（wikilink）＋ **概念頁 → 場景**（正文提及）。

## 快速開始

```bash
cd ~/services/scene-memory-backend

# 1. 建庫（掃場景 + 讀知識頁）
python3 backend/build_db.py --json

# 2. 開後端
node backend/server.mjs          # → http://127.0.0.1:8787
```

前端：`http://127.0.0.1:8787/`（`web/index.html`）

## API

| 端點 | 回傳 |
|---|---|
| `GET /api/meta` | 建庫時間、各表筆數、db 路徑與大小 |
| `GET /api/scenes` | 24 場景清單（檔案 metadata、技能、面板，不含全文） |
| `GET /api/scenes/:id` | 單一場景（含每個檔案全文） |
| `GET /api/scenes/:id/files/:name` | 單一檔案全文 |
| `GET /api/shared` | 共享層檔案（含內容） |
| `GET /api/concepts` | 13 概念頁（含 block 標題清單） |
| `GET /api/concepts/:slug` | 單一概念頁（含全文與所有 block） |
| `GET /api/graph` | `{nodes, edges}` 連結圖 |
| `GET /api/search?q=` | 跨場景 / 跨概念 / 跨檔案搜尋 |
| `GET /api/legacy.json` | **相容舊版 build_map.py payload**（給另一個 session 的互動設計圖一行改 fetch） |
| `GET /api/db.json` | 整包 JSON（靜態前端 fallback） |

## 資料表

```
scenes        場景主檔（id / name / path / has_git / handover_size / §₀ 全文）
scene_files   場景 × 記憶檔（role / layer / size / sha / content）  192 列
scene_skills  場景 × 專屬技能（size / desc）                        148 列
scene_panels  場景 × 面板（id / title / type）                       32 列
shared_files  共享層檔案（name / size / content）                    12 列
concepts      概念頁（slug / title / type / summary / tags / body）   13 列
concept_blocks 概念頁切成的區塊（heading / level / body）            98 列
edges         連結（concept→concept / concept→scene）                30 列
meta          建庫時間、來源路徑、筆數
```

## 檔案

```
backend/schema.sql      表結構（build 會 drop & recreate）
backend/build_db.py     建庫器：掃場景 + 讀 LLM-Wiki + 建 edges
backend/server.mjs      唯讀 REST API + 靜態檔
web/index.html          前端（fetch 版）
data/db.sqlite3         SQLite（1.1 MB）
data/db.json            靜態 fallback 匯出（622 KB）
scripts/refresh.sh      重建庫 + 重啟服務
```

## 維護

```bash
# 場景記憶改了之後刷新
bash scripts/refresh.sh

# 手動查
sqlite3 data/db.sqlite3 "select name,handover_size from scenes order by handover_size desc limit 5"
```

> ⚠️ **重建庫會 drop 所有表重來**。後端是唯讀的，所以沒有風險；
> 但若之後要加「使用者寫入的資料」（例如收藏、註記），那些表要另外設計，
> 不要塞進現有 schema 再靠 rebuild 保留。

## 怎麼讓「另一個 session 的互動設計圖」改用這個後端

舊版前端是把 JSON **內嵌進 HTML**（616 KB 單檔）：

```js
// build_map.py:178
const DB = __PAYLOAD__;
```

改成一行 fetch 即可，版面程式碼完全不用動：

```js
const DB = await (await fetch('http://127.0.0.1:8787/api/legacy.json')).json();
```

`/api/legacy.json` 保持與舊 payload **完全同構**（`generated_at` / `root` / `scene_count` / `shared{}` / `scenes[]`，每個 scene 含 `files{}` 與 `contents{}`），所以是純替換資料來源。

> 保留 `scan_scenes.py` → `build_map.py` 作為**離線快照**用途（例如寄給別人看、或做單檔分發）；日常改成打 API。

## Tailscale 掛載（已啟用）

```
https://garyaioserver.tail257fa5.ts.net/scene-memory/
```

- 只在 **tailnet 內**可達（`tailscale serve`，不是 `funnel` ⇒ 不會暴露到公網）
- 走 **HTTPS**，憑證由 Tailscale 自動簽發
- 只綁 `127.0.0.1:8787`，不開新的對外 port；對外流量全部由 tailscaled 代理

```bash
tailscale serve --bg --set-path=/scene-memory http://127.0.0.1:8787
tailscale serve status          # 看掛載
```

其他裝置（laptop-cneu6ssj / oppo-find-x9）連同一 tailnet 就能直接開那個網址。

> 前端的 API base 會從 `location.pathname` 推導，所以掛在子路徑下不用改任何設定。
> 如果將來要掛到別的路徑，改 `--set-path` 即可，前端自動跟上。

## 服務化（已啟用）

```ini
# ~/.config/systemd/user/scene-memory-backend.service
[Unit]
Description=Scene Memory Backend
After=network.target

[Service]
ExecStart=/usr/bin/node %h/services/scene-memory-backend/backend/server.mjs
WorkingDirectory=%h/services/scene-memory-backend
Restart=on-failure
Environment=PORT=8787 HOST=127.0.0.1

[Install]
WantedBy=default.target
```

```bash
cp deploy/scene-memory-backend.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now scene-memory-backend
```

已於 2026-11-09 啟用（開機自啟、`Restart=on-failure`）。
