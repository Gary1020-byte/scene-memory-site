-- 公開版資料庫：不含任何本機路徑、session id、私人記憶內容
PRAGMA journal_mode=WAL;

DROP TABLE IF EXISTS scenes;
DROP TABLE IF EXISTS scene_skills;
DROP TABLE IF EXISTS scene_panels;
DROP TABLE IF EXISTS layers;
DROP TABLE IF EXISTS reading;
DROP TABLE IF EXISTS meta;

CREATE TABLE scenes (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  purpose      TEXT NOT NULL,   -- 功用（一句話）
  detail       TEXT,            -- 完整職責描述
  boundary     TEXT,            -- 不碰什麼
  skill_count  INTEGER DEFAULT 0,
  file_count   INTEGER DEFAULT 0,
  panel_count  INTEGER DEFAULT 0,
  download     TEXT             -- 下載檔名
);

CREATE TABLE scene_skills (
  scene TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  name  TEXT NOT NULL,
  PRIMARY KEY (scene, name)
);

CREATE TABLE scene_panels (
  scene TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  id    TEXT NOT NULL,
  title TEXT,
  type  TEXT,
  PRIMARY KEY (scene, id)
);

-- L0..L5 六層架構
CREATE TABLE layers (
  id      INTEGER PRIMARY KEY,   -- 0..5
  code    TEXT NOT NULL,         -- L0
  title   TEXT NOT NULL,
  holds   TEXT NOT NULL,         -- 放什麼
  writer  TEXT NOT NULL,         -- 誰能寫
  note    TEXT,
  role    TEXT,                   -- 這層是什麼（一句話定位）
  rel     TEXT                    -- 與下一層的關係
);

-- 導讀文章（使用者自撰；未發布＝草稿）
CREATE TABLE reading (
  slug     TEXT PRIMARY KEY,
  seq      INTEGER NOT NULL,
  title    TEXT NOT NULL,
  status   TEXT NOT NULL,        -- draft | published
  body     TEXT
);

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
