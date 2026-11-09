-- Gary 的場景記憶架構 · 公開版資料庫（PostgreSQL）
-- 這個 schema 是「專門給這個站用的資料庫」，與機器上其他庫（hindsight / finance_lab）互不干擾。

CREATE SCHEMA IF NOT EXISTS scene_memory;
SET search_path TO scene_memory;

-- ─────────── 機器現況 ───────────
CREATE TABLE IF NOT EXISTS scenes (
  id           text PRIMARY KEY,
  name         text NOT NULL,
  purpose      text NOT NULL,      -- 功用（一句話）
  detail       text,                -- 完整職責描述
  boundary     text,                -- 不碰什麼
  skill_count  integer NOT NULL DEFAULT 0,
  file_count   integer NOT NULL DEFAULT 0,
  panel_count  integer NOT NULL DEFAULT 0,
  download     text,                -- 下載包檔名
  sort_order   integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scene_skills (
  scene text NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  name  text NOT NULL,
  PRIMARY KEY (scene, name)
);

CREATE TABLE IF NOT EXISTS scene_panels (
  scene text NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  id    text NOT NULL,
  title text,
  type  text,
  PRIMARY KEY (scene, id)
);

-- ─────────── 架構 ───────────
CREATE TABLE IF NOT EXISTS layers (
  id    integer PRIMARY KEY,        -- 0..5
  code  text NOT NULL UNIQUE,       -- L0
  title text NOT NULL,
  holds text NOT NULL,              -- 放什麼
  writer text NOT NULL,             -- 誰能寫
  note  text,                       -- 為什麼這樣
  role  text,                       -- 這層是什麼（一句話定位）
  rel   text                        -- 與下一層的關係
);

-- ─────────── 導讀文章 ───────────
CREATE TABLE IF NOT EXISTS reading (
  slug   text PRIMARY KEY,
  seq    integer NOT NULL UNIQUE,
  title  text NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
  body   text,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- ─────────── meta ───────────
CREATE TABLE IF NOT EXISTS meta (
  key   text PRIMARY KEY,
  value text
);

CREATE INDEX IF NOT EXISTS idx_scene_skills_scene ON scene_skills(scene);
CREATE INDEX IF NOT EXISTS idx_scene_panels_scene ON scene_panels(scene);
CREATE INDEX IF NOT EXISTS idx_reading_status ON reading(status);
