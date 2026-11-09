# Gary 的場景記憶架構 —— 公開版網站

> 記憶在檔案裡，不在會話裡。
> 一個場景就是一個 AI agent：共用一套規矩與台帳，各自有獨立記憶；
> 活按項目派給 owner，干完必須留證據和回執。

這是**只有公開版**的後端。它**不含任何本機狀態**：
沒有絕對路徑、沒有 session id、沒有場景私有記憶全文。

## 內容

| 端點 | 回傳 |
|---|---|
| `GET /api/meta` | 建庫時間、各表筆數 |
| `GET /api/scenes` | 24 個場景：功用、技能名、面板、下載連結 |
| `GET /api/layers` | L0–L5 六層架構（含定位與層間關係） |
| `GET /api/reading` | 導讀文章（slug／順序／標題／狀態／正文） |
| `GET /api/reading/:slug` | 單篇導讀 |
| `GET /downloads/<id>.zip` | 場景骨架包 |

## 資料來源

| | |
|---|---|
| 機器現況 | `~/.DSH/工作台/場景/`（掃描） |
| 場景描述 | `~/.DSH/工作台/外殼/scenarios/*.json` |
| 導讀文章 | `content/reading/*.md`（**作者自撰**） |

## 檔案

```
backend/schema_public.sql     表結構
backend/build_public.py       建庫器：掃場景 → 分表 → 產生下載包
backend/server_public.mjs     唯讀 REST API + 靜態網站
site/index.html               公開網站（Aurora 設計系統）
site/assets/                  Aurora token（vars-light/dark + components）
content/reading/              導讀文章來源（README 有格式說明）
public/downloads/             24 個場景骨架 zip（建庫時產生）
data/public.sqlite3           SQLite
scripts/refresh_public.sh     重建 + 重啟
deploy/*.service              systemd unit
```

## 發布新內容

```bash
# 寫好導讀文章到 content/reading/ 之後
bash scripts/refresh_public.sh
```

重建公開庫 → 重啟服務 → 印筆數。

**有內容＝已發布；空白＝「待撰寫」**（網站顯示佔位）。

## 服務

```bash
systemctl --user status scene-memory-backend-public
systemctl --user restart scene-memory-backend-public
```

Tailscale 掛載：

```bash
tailscale serve --bg --set-path=/scene-memory-public http://127.0.0.1:8788
```

目前是 **tailnet only**。要公開到網際網路需要 `tailscale funnel`（會把 443 開給全世界）
或搬到公開主機——那是另一個決定。

## 下載包內容

每個 zip 有 8 個檔案：`定位卡.md` / `AGENTS.md` / `場景私有記憶.md` /
`身份卡.md` / `場景畫像.md` / `_檔案索引.md` / `.dsh/skills/<id>/SKILL.md` / `README.md`。

**不含** `.git/`、不含本機路徑、不含 session id。使用者下載後自己 `git init` 就能用。
