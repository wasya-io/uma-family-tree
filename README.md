# uma-family-tree

JV-Link (JRA-VAN Data Lab.) の競走馬データから血統を **DAG (有向非巡回グラフ)** として構築し、
[3d-force-graph](https://github.com/vasturiano/3d-force-graph) で **3D フォースダイレクテッドグラフ**として
可視化する Web ビューアと、その事前加工パイプラインのモノレポ。

任意の馬を中心に据え、祖先・子孫の双方向を辿れる。ノードをタップして詳細を見たり、中心を切り替えたりできる。

本番: <https://uma-family-tree.pages.dev>

## 構成

| ディレクトリ | 役割 | 言語 / スタック |
|---|---|---|
| [`pipeline/`](./pipeline) | JV-Link 生データ → D1 投入用 SQL への加工 | Python |
| [`viewer/`](./viewer) | 3D 血統ビューア + データ API | SvelteKit + 3d-force-graph + Cloudflare Pages/D1 |
| [`docs/`](./docs) | ドキュメント (下記) | Markdown |
| `.kiro/steering/` | 常時参照する設計原則 | Markdown |

## ドキュメント

| 文書 | 内容 |
|---|---|
| [`docs/features.md`](./docs/features.md) | **機能一覧と使い方ガイド** (何ができるか・どう操作するか) |
| [`docs/data-model.md`](./docs/data-model.md) | **データモデルとたどり方** (D1 スキーマ・JV-Data 抽出・再帰 CTE) |
| [`docs/deploy.md`](./docs/deploy.md) | **本番デプロイ手順** (Cloudflare Pages + D1) |
| [`docs/design.md`](./docs/design.md) | 初期設計の記録 (履歴。一部は現状と異なる) |

## アーキテクチャ

```
[Windows] JV-Link ダンプ (UM/HN/SK/BT マスタ)
   ▼
[pipeline] Python 加工 (血統 DAG 構築 → D1 投入用 SQL 生成)
   ▼
[Cloudflare D1] horses / edges / keito_master / meta (隣接リスト)
   ▲  再帰 CTE で祖先/子孫を動的取得
   │
[Cloudflare Pages] viewer (SvelteKit) + Pages Functions API (/api/*)
```

血統の探索 (祖先 M 代 + 子孫 L 代) は D1 上の再帰 CTE で動的に行い、ビューアは組み立て処理を持たない。

## クイックスタート (ローカル)

```bash
# 加工パイプライン (Python / uv)
cd pipeline && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
.venv/bin/uma-pipeline --input ./input --output ./output   # pedigree.sql を生成

# ビューア (Node は Volta 経由)
cd viewer && npm install
./node_modules/.bin/wrangler d1 execute uma-family-tree --local --file=./db/schema.sql
./node_modules/.bin/wrangler d1 execute uma-family-tree --local --file=./db/pedigree.sql
npm run build && ./node_modules/.bin/wrangler pages dev .svelte-kit/cloudflare --port 5173
```

セットアップと主要コマンドの詳細は各 README ([`pipeline/README.md`](./pipeline/README.md) /
[`viewer/README.md`](./viewer/README.md))、デプロイは [`docs/deploy.md`](./docs/deploy.md) を参照。
