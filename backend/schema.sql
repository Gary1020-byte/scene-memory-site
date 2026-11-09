-- 場景記憶架構 · 後端資料庫 schema
-- 設計原則：規格/機器狀態（scenes）與知識（concepts）分表，
--           連結關係獨立成 edges 表，前端只做呈現。

PRAGMA journal_mode=WAL;

DROP TABLE IF EXISTS scenes;
DROP TABLE IF EXISTS scene_files;
DROP TABLE IF EXISTS scene_skills;
DROP TABLE IF EXISTS scene_panels;
DROP TABLE IF EXISTS shared_files;
DROP TABLE IF EXISTS concepts;
DROP TABLE IF EXISTS concept_blocks;
DROP TABLE IF EXISTS edges;
DROP TABLE IF EXISTS meta;

-- ─────────── 機器現況（由掃描器產生） ───────────
CREATE TABLE scenes (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  path         TEXT NOT NULL,
  has_git      INTEGER NOT NULL,
  handover_size INTEGER,
  handover_b64 TEXT,          -- §〇 交接全文
  skill_count  INTEGER DEFAULT 0,
  file_count   INTEGER DEFAULT 0,
  scanned_at   TEXT
);

CREATE TABLE scene_files (
  scene   TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  name    TEXT NOT NULL,
  kind    TEXT NOT NULL,      -- file | dir | missing
  role    TEXT,               -- 場景憲法 / 記憶真源 / …
  layer   TEXT,               -- 注入層 / 私有層 / 共享層
  desc    TEXT,
  size    INTEGER DEFAULT 0,
  sha     TEXT,
  count   INTEGER,            -- dir 內檔案數
  content TEXT,
  PRIMARY KEY (scene, name)
);

CREATE TABLE scene_skills (
  scene   TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  name    TEXT NOT NULL,
  size    INTEGER DEFAULT 0,
  desc    TEXT,
  PRIMARY KEY (scene, name)
);

CREATE TABLE scene_panels (
  scene   TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  id      TEXT NOT NULL,
  title   TEXT,
  type    TEXT,
  PRIMARY KEY (scene, id)
);

CREATE TABLE shared_files (
  name    TEXT PRIMARY KEY,
  size    INTEGER DEFAULT 0,
  content TEXT
);

-- ─────────── 知識（由 LLM-Wiki 攝入） ───────────
CREATE TABLE concepts (
  slug     TEXT PRIMARY KEY,
  title    TEXT NOT NULL,
  type     TEXT NOT NULL,      -- overview | entity | concept | comparison
  path     TEXT,
  summary  TEXT,               -- frontmatter 下方第一段
  tags     TEXT,
  body     TEXT,
  order_no INTEGER
);

CREATE TABLE concept_blocks (
  slug    TEXT NOT NULL REFERENCES concepts(slug) ON DELETE CASCADE,
  idx     INTEGER NOT NULL,
  heading TEXT,
  level   INTEGER,
  body    TEXT,
  PRIMARY KEY (slug, idx)
);

-- ─────────── 連結（wikilink 圖） ───────────
CREATE TABLE edges (
  src   TEXT NOT NULL,
  dst   TEXT NOT NULL,
  kind  TEXT NOT NULL,   -- concept→concept (wikilink) | scene→concept (mention)
  label TEXT,
  PRIMARY KEY (src, dst, kind)
);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
