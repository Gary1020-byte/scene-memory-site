# 導讀文章

這裡放你要寫的導讀文章。**一篇一個 .md**，檔名對應 slug：

```
01-what-is-this.md
02-why-scenes.md
03-three-layers.md
04-boundaries.md
05-handover.md
06-dispatch.md
07-accumulable.md
08-sovereignty.md
09-single-source.md
10-workflow.md
11-scene-vs-subagent.md
12-ledger-vs-wiki.md
```

## 怎麼發布

寫好後執行：

```bash
bash scripts/refresh_public.sh
```

那會：重建公開資料庫 → 重啟公開服務。

**檔案有內容＝已發布，空白＝「待撰寫」**（網站上會顯示為待撰寫的佔位）。

## 格式

普通 Markdown，網站端支援：標題、段落、清單、表格、程式碼、引用、粗體、行內程式碼。
