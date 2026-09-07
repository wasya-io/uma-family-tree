# 設計メモ — uma-family-tree

> ⚠️ **この文書は初期設計 (R2 + 静的 JSON 配信) の記録で、一部は現状と異なる。**
> その後 Cloudflare **D1 (SQLite) + Pages Functions** に移行し、事前展開 JSON ではなく
> 再帰 CTE による動的取得に変わった。現状のデータモデル・探索方法は
> **[`data-model.md`](./data-model.md)**、機能は **[`features.md`](./features.md)**、
> デプロイは **[`deploy.md`](./deploy.md)** を参照。
> 本文書は設計判断の経緯 (特に §1 JV-Data 構造、§5 実データ確定事項) を残す履歴として維持する。

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

## 5. 実データ確定事項 (2026-09 実データ取得後)

JV-Link から取得した実データ (UM 198,212 / HN 153,798 / BT 92 レコード) に基づき確定:

- **繁殖登録番号は 8 桁フォーマット**。JVData_Struct.py (2026版) は 10 桁前提だが、実データは
  8 桁で HN/BT のオフセットが 2 バイトずつ手前にずれる。確定オフセットは `records.py` に記載。
  参照整合性検証 (HN.FNum → HN.HansyokuNum) で 100% 一致を確認済み。
- **ノード一意キー = HansyokuNum** (`node_id = "H" + HansyokuNum`)。血統リンクは繁殖登録番号
  で張られ、KettoNum は競走馬にしか無い (サンデーサイレンス等の輸入種牡馬は KettoNum 無し)。
  KettoNum は検索/URL 用の補助属性としてノードに併記。
- **系統色分け**: BT レコードは系統代表馬 92 件のみ。各馬へは父方をさかのぼって最初に見つかる
  KeitoId を継承 (`graph._propagate_keito`)。付与率 88.5%。KeitoId は「2桁ごとの階層 ID」
  (例 01080201010201 = サンデーサイレンス系)。keito-master は出現数上位 N をパレット着色。
- **グラフ規模**: 153,798 ノード / 282,676 親子エッジ。構築 1.3 秒。
- **世代ウィンドウの妥当性を実データで確認**: ゴールドシップ 祖先5代=61/子孫3代=10ノード、
  ディープインパクト 子孫3代=950、**サンデーサイレンス 子孫3代=10,952**。子孫方向の爆発が
  大きく、N世代ウィンドウ + 全部盛り限定 の方針が正しいことを裏付け。

### 残課題

- **系統の丸め粒度**: 現状は KeitoId (階層 ID) の完全一致で上位 N 着色。より大きな「主要系統」
  に丸めるなら KeitoId の接頭辞 (先頭 4〜6 桁) でグルーピングする案。実表示を見て調整。
- **検索インデックスの規模**: 全 153k ノードで `search-index.json` が約 15MB。ブラウザ一括
  ロードは重いので、prefix 分割 or サーバ側検索 (Pages Functions) を検討。
- **馬ファイルの全件生成**: 153k ノード全部の `horses/*.json` を出すとファイル数が過大。
  R2 配置戦略 (全件事前生成 vs オンデマンド生成) を決める必要がある。当面は `--only` /
  `--limit` で対象を絞って生成・検証。
- **CORS 許可オリジン**: Cloudflare Pages 本番ドメイン + `http://localhost:5173`。

## 6. 加工・デプロイ手順 (概要、詳細は pipeline/README で整備)

1. Windows で JV-Link を使い UM/HN/SK/BT マスタをダンプ。
2. 生データを `pipeline/input/` に配置。
3. `pipeline` を実行して `pipeline/output/` に JSON 群を生成。
4. 生成物を R2 バケットにアップロード (全部盛りは viewer/static でも可)。
5. R2 バケットに独自ドメインのサブドメインをカスタムドメインとして割り当て、CORS を設定。
6. `viewer` の `PUBLIC_DATA_BASE_URL` を配信ドメインに設定して Cloudflare Pages にデプロイ。
