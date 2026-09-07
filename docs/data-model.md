# データモデルとたどり方

血統データがどう格納され、どう辿られるかの詳説。実装 (`pipeline/`, `viewer/db/`,
`viewer/src/lib/server/pedigree.ts`) に対応する「データの真実の源」。

> 配信は Cloudflare **D1 (SQLite)** + Pages Functions。以前の R2 + 静的 JSON 構成からの
> 移行後の現状を記す (旧設計は `docs/design.md` に履歴として残置)。

---

## 1. 全体像

```
[Windows] JV-Link ダンプ (UM/HN/SK/BT の .dat + lastfiletime.txt)
   │
   ▼
[pipeline] Python 加工: パース → 血統 DAG 構築 → D1 投入用 SQL 生成
   │  (pipeline/output/pedigree.sql)
   ▼
[Cloudflare D1] horses / edges / keito_master / meta
   ▲  再帰 CTE で祖先/子孫を動的に取得
   │
[Pages Functions] /api/* が D1 を引いて JSON を返す
   ▼
[viewer] 3d-force-graph で描画
```

血統は本来「世代ごとに2倍の二分木」だが、インブリード (同一祖先が複数箇所に登場) を
1 ノードに集約するため **DAG** として扱う。テーブルには階層を畳まず、隣接リスト
(ノード + エッジ) で持ち、祖先/子孫の展開は問い合わせ時に再帰 CTE で行う。

---

## 2. D1 スキーマ

定義: `viewer/db/schema.sql`。

### horses (馬ノード)

| 列 | 型 | 意味 |
|---|---|---|
| `id` | TEXT PK | ノード一意キー。`"H" + 繁殖登録番号 (HansyokuNum)`。 |
| `ketto_num` | TEXT | 血統登録番号 (競走馬のみ)。検索/URL 共有の補助。繁殖のみの馬は空。 |
| `name` / `kana` / `eng` | TEXT | 馬名 (漢字 / 半角カナ / 欧字)。 |
| `sex` | TEXT | 性別 (牡/牝/セン)。デコード済み。 |
| `color` | TEXT | 毛色。デコード済み。 |
| `birth_year` | INTEGER | 生年。 |
| `keito_id` | TEXT | 系統ID (色分けキー)。未知は `"other"`。 |
| `earnings` | INTEGER | 平地本賞金累計。**単位は 100 円** (JV-Data の生値)。競走実績なしは 0。 |
| `wins` | INTEGER | 総合1着回数。競走実績なしは 0。 |

### edges (親子エッジ)

| 列 | 型 | 意味 |
|---|---|---|
| `parent_id` | TEXT | 親ノード id。 |
| `child_id` | TEXT | 子ノード id。 |
| `parent` | TEXT | `'father'` | `'mother'`。 |

PRIMARY KEY (`parent_id`, `child_id`)。

### keito_master (系統マスタ)

| 列 | 型 | 意味 |
|---|---|---|
| `keito_id` | TEXT PK | 系統ID。 |
| `name` | TEXT | 系統名。 |
| `color` | TEXT | 色 (#RRGGBB)。 |

### meta (メタ情報)

`key` / `value` の汎用表。現状は `data_timestamp` = データ基準時点 (`YYYYMMDDhhmmss`) を保持。

### インデックス

```
idx_edges_child  ON edges(child_id)    -- 祖先方向 (子→親)
idx_edges_parent ON edges(parent_id)   -- 子孫方向 (親→子)
idx_horses_kana / idx_horses_name / idx_horses_ketto  -- 検索
```

### 規模 (2023-07-31 時点データ)

horses 153,798 / edges 282,676 / keito 21 (主要20 + other) / meta 1。
earnings>0 が 25,126 頭、wins>0 が 17,922 頭 (残りは繁殖のみで競走実績なし)。

---

## 3. JV-Data からの抽出 (pipeline)

入力: `pipeline/input/` に置いた UM/HN/SK/BT の .dat (cp932 固定長, CR/LF 区切り) と
`lastfiletime.txt` (データ基準時点)。パースは `pipeline/src/uma_pipeline/records.py`。

| レコード | 構造体 | キー | 使う情報 |
|---|---|---|---|
| UM 競走馬マスタ | `JV_UM_UMA` | KettoNum (10桁) | 馬名/カナ/英字, 性別, 毛色, 生年, 3代血統, **実績 (賞金・着回数)** |
| HN 繁殖馬マスタ | `JV_HN_HANSYOKU` | HansyokuNum | 父/母の繁殖番号 (親ポインタ), KettoNum, 馬名等 |
| BT 系統情報 | `JV_BT_KEITO` | HansyokuNum | KeitoId, KeitoName |
| SK 産駒マスタ | `JV_SK_SANKU` | KettoNum | (現状未使用。将来の補完用) |

### 重要: 繁殖登録番号は 8 桁フォーマット

`JVData_Struct.py` (SDK 2026版) は繁殖登録番号を **10 桁**前提でオフセットを組むが、今回取得した
実データは **8 桁**。そのため HN/BT のオフセットは仕様から 2 バイトずつ手前にずれる。確定オフセットは
`records.py` に記載し、参照整合性検証 (HN.FNum → HN.HansyokuNum が 100% 一致) で確定済み。

### 実績フィールド (UM) のオフセット

UM.dat は実データで **1575 バイト固定長** (SDK の 10 桁前提 ~1608 とずれる)。実データで実証した位置:

| 項目 | オフセット | 備考 |
|---|---|---|
| 平地本賞金累計 | `[1021, 9]` | → `earnings` (100 円単位) |
| 総合着回数 | `[1075, 3×6]` | [1着,2着,3着,4着,5着,着外] の各3桁。先頭 = `wins` |
| 登録レース数 | `[1573, 3]` | 現状未使用 |

検証: キタサンブラック 総合着回数 `012,002,004,000,000,002` (20戦12勝) / 本賞金 `018132000`、
ディープインパクト (14戦12勝) / `013240000`。

> 「重賞勝ち」そのものを示すフィールドは UM に無い。獲得賞金・勝利数を実績の近似指標として使う
> (重賞を勝てば賞金が大きいので相関が高い)。厳密な重賞/G1 勝ち数が要るなら RA (レース詳細の
> GradeCD) + SE (馬毎レース情報の確定着順) の追加取得が必要。

### グラフ構築 (`graph.py`)

- **ノード一意キー = HansyokuNum** (`node_id = "H" + HansyokuNum`)。血統リンクは繁殖登録番号で
  張られ、KettoNum は競走馬にしか無い (輸入種牡馬等は KettoNum 無し) ため。
- HN の親ポインタでエッジを張り、UM の表示情報 (馬名・性別・毛色・生年・**賞金・勝利数**) で
  ノードを強化 (KettoNum で紐付け)。
- 系統: BT は系統代表馬のみ (実データ 92 件)。各馬へ **父方をさかのぼって最初に見つかる KeitoId を
  継承** (`_propagate_keito`)。keito-master は出現数上位を主要系統として着色、残りは `other`。

### SQL 生成 (`emit.py`)

`horses` / `edges` / `keito_master` / `meta` の INSERT を `pedigree.sql` に出力。
複数行 VALUES でまとめる。**Cloudflare D1 (remote) は `BEGIN TRANSACTION`/`COMMIT`/`SAVEPOINT` を
受け付けない**ため、トランザクション制御文は出力しない (投入手順は `docs/deploy.md`)。

---

## 4. 祖先/子孫のたどり方 (再帰 CTE)

実装: `viewer/src/lib/server/pedigree.ts` の `fetchPedigree()`。API `/api/horse/[id]` から呼ばれる。

### パラメータ

| 名前 | 既定 | 意味 |
|---|---|---|
| `anc` (ancDepth) | 5 | 祖先を何代辿るか。子表示モードは 0 (祖先なし)。0..8 にクランプ。 |
| `desc` (descDepth) | 1 | 子孫を何代辿るか。子表示モードは 1..3。0..8 にクランプ。 |
| `full` | false | 代表子への絞り込みを解除し全子孫を辿る (重い)。 |

### 世代の符号

中心 = `generation 0`、祖先 = `+n`、子孫 = `-n`。同一 id が複数世代に出たら |generation| 最小を採用。

### D1 のバインド上限への対応

D1 は 1 クエリのバインドパラメータ上限が小さい (~100)。id を並べて `IN (?, ?, …)` する方式は使わず、
**再帰 CTE を JOIN** して求め、バインドは `centerId` + 深さの **3 個に固定**している。
(以前 ids を 2 回バインドして D1 エラーになった経緯があるため、ids は 1 回だけ bind する。)

### 代表子孫の優先 (賞金順) と間引き

種牡馬は子孫が指数的に増える。表示破綻を防ぐため 2 段階で絞る:

1. **中心の直仔**: 直仔数が `CHILD_THRESHOLD` (40) を超え、かつ `full` でなければ、
   `REPRESENTATIVE_CHILDREN` (40) 頭に絞る。順序は
   **獲得賞金 DESC → 勝利数 DESC → 子孫を持つ子を優先 → 生年 DESC → id**。
2. **孫以降の枝分かれ (fanout)**: `full` でなく子孫を 2 代以上辿るとき、各親から
   賞金上位 `DESC_FANOUT` (8) 頭のみ辿る。`ranked_edges` CTE で
   `ROW_NUMBER() OVER (PARTITION BY parent_id ORDER BY earnings DESC, …)` を振り、`rn <= 8` を辿る。

効果: サンデーサイレンス desc=3 が 5,374 → 508 ノードに収まる。定数は pedigree.ts の先頭に定義。

### maxDescDepth (世代スイッチャーの制御用)

meta に `maxDescDepth` (代表子孫を辿って実際にデータが存在する最大の子孫世代, 0..3) を返す。
若い種牡馬 (例: ゴールドシップ 2009年生) は孫がまだ存在せず `maxDescDepth = 1`。viewer は
これを超える世代ボタンを無効化し注記を出す。現在の `desc` に依らず一定値を返すため、まず
レスポンスの到達深さから求め、まだ先がありうる場合のみ深さのみを追加クエリで確認する。

### レスポンス形 (`HorseGraph`)

```jsonc
{
  "center": "H11202369",
  "nodes": [ { "id","kettoNum","name","kana","eng","sex","color","birthYear",
               "keitoId","generation","earnings","wins" } ],
  "edges": [ { "source","target","parent" } ],
  "meta":  { "truncatedChildren": bool, "totalChildren": int, "maxDescDepth": int }
}
```

---

## 5. API エンドポイント (Pages Functions)

| エンドポイント | 役割 | キャッシュ |
|---|---|---|
| `GET /api/horse/[id]?anc=&desc=&full=` | 中心馬 + 祖先/子孫。404 対応 | 5 分 |
| `GET /api/search?q=` | カナ/名前/血統番号の LIKE 検索 (20件) | — |
| `GET /api/keito` | 系統マスタ (色分け) | 1 日 |
| `GET /api/exists/[id]` | 馬の存在確認 (中心切替ボタンの活性判定) | — |
| `GET /api/meta` | メタ情報 (データ基準時点 など) | — |

D1 バインディングは `platform.env.DB` (`viewer/src/app.d.ts` の `App.Platform`)。

---

## 6. データ更新の流れ

1. Windows で JV-Link を使い UM/HN/SK/BT + lastfiletime.txt を再取得し `pipeline/input/` に配置。
2. `pipeline` で `pedigree.sql` を再生成し `viewer/db/` にコピー。
3. スキーマ変更を伴う場合は D1 のテーブルを作り直す (列追加は `CREATE TABLE IF NOT EXISTS` では
   反映されないため DROP → schema → data の順)。
4. 本番 D1 へ投入し、viewer をビルド・デプロイ。

詳細な手順・コマンドは **[`deploy.md`](./deploy.md)**。
