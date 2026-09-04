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

1. JV-Link がダンプした生データを `input/` に配置する。
2. パイプラインを実行:

   ```bash
   uma-pipeline --input ./input --output ./output
   ```

3. `output/` に以下が生成される:

   | 生成物 | 内容 |
   |---|---|
   | `horses/{KettoNum}.json` | 馬ノードファイル (祖先 M 代 + 子孫 L 代を事前展開) |
   | `search-index.json` | 検索辞書 (カナ/英字 → KettoNum) |
   | `keito-master.json` | 系統マスタ (KeitoId → 系統名 + 色) |
   | `full/{KettoNum}.json` | 全部盛り専用ファイル (限定始祖の全子孫) |

4. `output/` を R2 バケットにアップロードする (デプロイ手順は `docs/design.md` §6)。

## モジュール構成

| モジュール | 役割 |
|---|---|
| `uma_pipeline.records` | JV-Data レコード (UM/HN/SK/BT) のパース |
| `uma_pipeline.graph` | パース結果から血統 DAG (ノード + 親子エッジ + 逆引き) を構築 |
| `uma_pipeline.keito` | 系統 (BT) を集計し、主要系統に丸めた系統マスタを生成 |
| `uma_pipeline.emit` | DAG から各種 JSON を書き出し |
| `uma_pipeline.codes` | SexCD / KeiroCD などコード値のデコード表 |
| `uma_pipeline.cli` | エントリポイント (入出力パス・深さの指定) |

## 現状

雛形 (スキャフォールド)。各モジュールはインターフェースと TODO を定義済み。
実データ (input) が用意でき次第、パース・DAG 構築・出力の中身を実装する。
