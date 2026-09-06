# pipeline — データ加工パイプライン

JV-Link (JRA-VAN Data Lab.) がダンプした生データ (UM/HN/SK/BT マスタ) を入力に取り、
血統 DAG を構築して配信用 JSON 群を生成する Python パイプライン。

## 前提

- データ取得 (JV-Link を叩いて生データをダンプ) は **Windows マシン**で行う (本パイプラインの対象外)。
- 本パイプラインは、ダンプ済みの生データファイルを入力に取り、プラットフォーム非依存で動作する。

## セットアップ

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## 使い方

1. JV-Link がダンプした生データを `input/` に配置する
   (UM/HN/SK/BT の .dat と、データ基準時点を示す `lastfiletime.txt`)。
2. パイプラインを実行:

   ```bash
   .venv/bin/uma-pipeline --input ./input --output ./output
   ```

3. `output/pedigree.sql` が生成される (Cloudflare D1 投入用の SQL)。
   `horses` / `edges` / `keito_master` / `meta` の INSERT 文をトランザクションで囲んだもの。

   | テーブル | 内容 |
   |---|---|
   | `horses` | 馬ノード (id="H"+繁殖番号、名前/カナ/性別/毛色/生年/系統ID) |
   | `edges` | 親子エッジ (parent_id → child_id, parent='father'\|'mother') |
   | `keito_master` | 系統マスタ (主要系統に丸めた KeitoId → 系統名 + 色) |
   | `meta` | `data_timestamp` = `lastfiletime.txt` の値 (データ基準時点) |

4. 生成した SQL を `viewer/db/pedigree.sql` にコピーし、D1 に投入する
   (投入・デプロイ手順は [`../docs/deploy.md`](../docs/deploy.md))。

   ```bash
   cp output/pedigree.sql ../viewer/db/pedigree.sql
   ```

## モジュール構成

| モジュール | 役割 |
|---|---|
| `uma_pipeline.records` | JV-Data レコード (UM/HN/SK/BT) のパース |
| `uma_pipeline.graph` | パース結果から血統 DAG (ノード + 親子エッジ + 逆引き) を構築 |
| `uma_pipeline.keito` | 系統 (BT) を集計し、主要系統に丸めた系統マスタを生成 |
| `uma_pipeline.emit` | DAG から D1 投入用 SQL (`write_sql`) を書き出し |
| `uma_pipeline.codes` | SexCD / KeiroCD などコード値のデコード表 |
| `uma_pipeline.cli` | エントリポイント (入出力パス・SQL ファイル名の指定) |

## 現状

実装済み。実データ (horses 153,798 / edges 282,676 / keito 21) で SQL 生成を確認済み。
