# uma-family-tree

JV-Link (JRA-VAN Data Lab.) の競走馬データから血統を **DAG (有向非巡回グラフ)** として構築し、
[3d-force-graph](https://github.com/vasturiano/3d-force-graph) で **3D フォースダイレクテッドグラフ**として
可視化する Web ビューアと、その事前加工パイプラインのモノレポ。

任意の馬を中心に据え、祖先・子孫の双方向を辿れる。ノードをタップすると中心が切り替わる。

## 構成

| ディレクトリ | 役割 | 言語 / スタック |
|---|---|---|
| [`pipeline/`](./pipeline) | JV-Link 生データ → 配信用 JSON への加工 | Python |
| [`viewer/`](./viewer) | 3D 血統ビューア (Cloudflare Pages) | SvelteKit + 3d-force-graph |
| [`docs/`](./docs) | 設計メモ | Markdown |
| `.kiro/steering/` | 常時参照する設計原則 | Markdown |

## データフロー

```
[Windows] JV-Link ダンプ (UM/HN/SK/BT マスタ)
   ▼
[pipeline] Python 加工 (DAG 構築 → 分割 JSON 生成)
   ▼
[R2] data.<独自ドメイン> で配信 (CORS)
   ▼
[Cloudflare Pages] viewer が fetch して 3D 描画
```

詳細は [`docs/design.md`](./docs/design.md) と `.kiro/steering/` を参照。

## クイックスタート

```bash
# 加工パイプライン
cd pipeline && python -m venv .venv && . .venv/bin/activate && pip install -e .

# ビューア
cd viewer && npm install && npm run dev
```
