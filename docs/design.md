# 設計メモ — uma-family-tree

議論で確定した要件・設計の詳細。steering (`.kiro/steering/`) が「常時参照する原則」なのに対し、
本ドキュメントは確定仕様・データ形式・未確定事項の記録を目的とする。

## 1. データ源 (JV-Data)

JV-Link SDK の構造体定義 (`.refarence/.../JV-Data構造体/Python版/JVData_Struct.py`) より、血統に関わるレコード:

| レコード | 構造体 | キー | 血統に使う要素 |
|---|---|---|---|
| 競走馬マスタ | `JV_UM_UMA` | `KettoNum` (血統登録番号10桁) | `Ketto3Info` (3代血統14頭: HansyokuNum + Bamei)、馬名/カナ/英字、性別、毛色、生年月日 |
| 繁殖馬マスタ | `JV_HN_HANSYOKU` | `HansyokuNum` (繁殖登録番号10桁) | `HansyokuFNum` (父の繁殖番号)、`HansyokuMNum` (母の繁殖番号)、`KettoNum`、馬名/カナ/英字、性別、毛色、生年 |
| 産駒マスタ | `JV_SK_SANKU` | `KettoNum` | `HansyokuNum[14]` (3代血統の繁殖番号) |
| 系統情報 | `JV_BT_KEITO` | `HansyokuNum` | `KeitoId` (系統ID10桁)、`KeitoName` (系統名)、`KeitoEx` (系統説明) |

### 重要な設計上の含意

- **繁殖馬マスタの親ポインタ (`HansyokuFNum` / `HansyokuMNum`) を再帰的に辿ることで、世代制限なく祖先を遡れる。**
  UM の `Ketto3Info` は3代までだが、HN を辿れば任意の深さまで到達できる。
- **子孫方向**は、HN の親ポインタを「子 → 親」の逆リンクとして全馬から集約し、逆引きインデックスを作ることで辿る。
- **KettoNum と HansyokuNum は別体系**。繁殖入りした馬は両方を持つ (HN に両方が入っている)。
  ノードの一意キーをどちらにするかは正規化方針で決める (下記 §3)。
- **系統は JV-VAN が既に分類済み** (`HansyokuNum → KeitoId/KeitoName`)。自前分類は不要。色分けは出現数上位を固有色、他は「その他」に丸める。

## 2. アーキテクチャ

確定事項 (steering `structure.md` 参照)。モノレポ = `pipeline/` (Python 加工) + `viewer/` (SvelteKit)。
配信は R2 (公開バケット + 独自ドメインのサブドメイン `data.<domain>`、CORS 設定)。

## 3. 生成データ形式 (pipeline → R2)

### 3.1 馬ノードファイル `horses/{KettoNum}.json`

その馬を中心にしたとき表示する範囲 (祖先 M 代 + 子孫 L 代) を事前展開したサブグラフ。
デフォルト M/L は要調整 (§5 未確定)。UI の深さ最大値まで事前展開しておく方針 (案B折衷)。

```jsonc
{
  "center": "0000000000",         // 中心馬の KettoNum
  "nodes": [
    {
      "id": "0000000000",          // KettoNum (繁殖のみの馬は HansyokuNum 由来の代替IDになる可能性 — §3.3)
      "name": "ゴールドシップ",
      "kana": "ゴールドシップ",
      "eng": "Gold Ship",
      "sex": "牡",                 // SexCD をデコード
      "color": "芦毛",             // KeiroCD をデコード
      "birthYear": 2009,
      "keitoId": "xxxxxxxxxx",     // 系統ID (色分けキー)
      "generation": 0              // 中心=0, 祖先=+1..+M, 子孫=-1..-L
    }
  ],
  "edges": [
    {
      "source": "<親のid>",
      "target": "<子のid>",
      "parent": "father" | "mother"   // 父方=青細線, 母方=赤太線+粒子
    }
  ]
}
```

- インブリード (クロス) は、同一 `id` のノードに複数の子から `edges` が集まることで自然に表現される
  (DAG として1ノード集約)。ビューアが「入次数(子側からの参照)が複数のノード」を検出して強調表示する。

### 3.2 検索インデックス `search-index.json`

```jsonc
[
  { "id": "0000000000", "kana": "ゴールドシップ", "eng": "Gold Ship" }
]
```

- カナ + 英字でインクリメンタルサーチ。母集団が大きい場合は分割 / prefix 化を検討 (§5 未確定)。

### 3.3 系統マスタ `keito-master.json`

```jsonc
{
  "xxxxxxxxxx": { "name": "サンデーサイレンス系", "color": "#e6194b" },
  "other":      { "name": "その他",             "color": "#999999" }
}
```

- pipeline が全馬の `KeitoId` 出現数を集計 → 上位 N 系統に固有色、残りは `other`。N と配色は実データ確認後に確定。

### 3.4 全部盛りファイル `full/{KettoNum}.json`

- 主要始祖 (サンデーサイレンス、ノーザンダンサー等) について全子孫を1ファイルに展開。
- 対象は限定リストで管理し、リストに1件追加 + ファイル生成で対象を増やせる。
- 数千ノード規模のため、ビューアは LOD (球のみ・ラベル省略) で描画する。
- 形式は 3.1 と同じ nodes/edges だが範囲が「全子孫」。ファイル数が少ないので viewer/static 配置も可。

## 4. ビュー仕様 (viewer)

- 表示戦略: **N世代ウィンドウ** (祖先何代・子孫何代を UI で調整)。中心タップで再センタリング (該当ファイル再ロード)。
- ノード: 馬名・性別・毛色を表示。色分けは系統 (`keitoId` → `keito-master.json` の色)。
- リンク: 父方=青細線 / 母方=赤太線+流れる粒子。祖先方向 / 子孫方向。
  (当初「父=実線/母=破線」を想定したが、3d-force-graph には 3D 破線 API (`linkLineDash`) が無いため色・太さ・粒子で区別する。)
- インブリード強調: 複数の子から集まる同一ノードを太線・発光等で強調。
- 全部盛りモード: 限定馬の専用ファイルをロード、LOD 描画。低優先で実装。
- 検索: カナ + 英字のインクリメンタルサーチ → 中心指定。
- URL 共有: `/?horse={KettoNum}`。
- 配信ベース URL: 環境変数 `PUBLIC_DATA_BASE_URL`。

## 5. 未確定事項 (後続で詰める)

- **系統の丸め上位 N と配色**: 実データの `JV_BT_KEITO` 系統数を集計して決定。
- **N世代ウィンドウのデフォルト深さ / 事前展開の M・L 値**: 体感を見て調整。
  たたき台として「祖先5代 + 子孫3代」を事前展開の最大範囲とする案。
- **検索インデックスの規模対策**: 母集団 (対象馬数) が確定してから分割要否を判断。
  当面は「好きな馬 + その血統圏 (数百〜数千頭)」規模を想定。
- **ノード一意キーの正規化**: KettoNum を持たない繁殖のみの馬 (古い始祖等) の扱い。
  HansyokuNum → 代替 id へのマッピング規約を pipeline 実装時に確定する。
- **CORS 許可オリジン**: Cloudflare Pages 本番ドメイン + `http://localhost:5173` (ローカル開発)。

## 6. 加工・デプロイ手順 (概要、詳細は pipeline/README で整備)

1. Windows で JV-Link を使い UM/HN/SK/BT マスタをダンプ。
2. 生データを `pipeline/input/` に配置。
3. `pipeline` を実行して `pipeline/output/` に JSON 群を生成。
4. 生成物を R2 バケットにアップロード (全部盛りは viewer/static でも可)。
5. R2 バケットに独自ドメインのサブドメインをカスタムドメインとして割り当て、CORS を設定。
6. `viewer` の `PUBLIC_DATA_BASE_URL` を配信ドメインに設定して Cloudflare Pages にデプロイ。
