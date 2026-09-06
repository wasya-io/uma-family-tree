-- 血統 DAG の D1 スキーマ。
-- 隣接リスト (nodes + edges) で表現。階層をテーブルに畳まないので深さ無制限。
-- 祖先/子孫の探索は Pages Functions 側の再帰 CTE で行う。

-- 馬 (ノード)
CREATE TABLE IF NOT EXISTS horses (
  id          TEXT PRIMARY KEY,   -- "H" + 繁殖登録番号
  ketto_num   TEXT,               -- 血統登録番号 (競走馬のみ)。検索/表示補助。
  name        TEXT,
  kana        TEXT,
  eng         TEXT,
  sex         TEXT,               -- デコード済み (牡/牝/セン)
  color       TEXT,               -- デコード済み毛色
  birth_year  INTEGER,
  keito_id    TEXT                -- 系統ID (色分けキー)
);

-- 親子エッジ (親 -> 子)
CREATE TABLE IF NOT EXISTS edges (
  parent_id   TEXT NOT NULL,
  child_id    TEXT NOT NULL,
  parent      TEXT NOT NULL,      -- 'father' | 'mother'
  PRIMARY KEY (parent_id, child_id)
);

-- 系統マスタ (色分け)
CREATE TABLE IF NOT EXISTS keito_master (
  keito_id    TEXT PRIMARY KEY,
  name        TEXT,
  color       TEXT
);

-- 探索用インデックス (再帰CTEの rows_read を抑える要)
CREATE INDEX IF NOT EXISTS idx_edges_child  ON edges(child_id);   -- 祖先方向: 子から親を引く
CREATE INDEX IF NOT EXISTS idx_edges_parent ON edges(parent_id);  -- 子孫方向: 親から子を引く

-- 検索用インデックス
CREATE INDEX IF NOT EXISTS idx_horses_kana ON horses(kana);
CREATE INDEX IF NOT EXISTS idx_horses_name ON horses(name);
CREATE INDEX IF NOT EXISTS idx_horses_ketto ON horses(ketto_num);
