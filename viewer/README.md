# viewer — 3D 血統ビューア

SvelteKit + [3d-force-graph](https://github.com/vasturiano/3d-force-graph) で血統 DAG を 3D 表示する
Cloudflare Pages 向けフロントエンド。データは R2 から fetch する (組み立て処理は持たない)。

## セットアップ

```bash
npm install
cp .env.example .env      # PUBLIC_DATA_BASE_URL を配信ドメインに設定
npm run dev
```

> 注: このリポジトリは Node/npm 未導入の環境で雛形作成された。初回は `npm install` が必要。
> SvelteKit の型ファイル (`.svelte-kit/`) は `npm run dev` / `svelte-kit sync` で自動生成される。

## 環境変数

| 変数 | 用途 |
|---|---|
| `PUBLIC_DATA_BASE_URL` | データ配信ベース URL (R2 カスタムドメイン `https://data.<domain>`)。暫定で `r2.dev` も可。 |

## 構成

| ファイル | 役割 |
|---|---|
| `src/lib/types.ts` | 配信 JSON のデータ契約 (pipeline の出力と対応) |
| `src/lib/data.ts` | R2 からの fetch クライアント |
| `src/lib/graph.ts` | 3d-force-graph ラッパ (色分け・父母リンク・インブリード強調・中心切り替え) |
| `src/lib/HorseSearch.svelte` | カナ/英字インクリメンタルサーチ |
| `src/routes/+page.svelte` | メイン画面 (グラフ + 検索 + URL 同期 `?horse=`) |

## 機能

- 系統 (keitoId) によるノード色分け。中心馬は強調。
- リンク: 父方=青の細線 / 母方=赤の太線 + 流れる粒子 (3D では破線が扱えないため色・太さ・粒子で区別)。
- インブリード (複数の子から集まる同一ノード) を強調。
- ノードクリックで中心切り替え (URL `?horse=` を更新 → 共有可能)。
- 検索: カナ + 英字のインクリメンタルサーチ。

## デプロイ (Cloudflare Pages)

- `@sveltejs/adapter-static` で完全静的サイトとして出力する (SSR/Workers 不要、wrangler 不要)。
- ビルドコマンド `npm run build`、出力ディレクトリ `build/`。
- Cloudflare Pages では「フレームワークプリセット: SvelteKit」または直接 `build/` を配信対象に指定。
- R2 バケットの CORS 許可オリジンに、本番 Pages ドメインと `http://localhost:5173` を含める。

## ローカルでの実行 (Node をホストに入れない場合)

Docker 経由で実行できる:

```bash
# 依存インストール + ビルド
docker run --rm -v "$PWD":/app -w /app node:20-alpine sh -c "npm install && npm run build"
# 開発サーバ (ポート公開)
docker run --rm -it -p 5173:5173 -v "$PWD":/app -w /app node:20-alpine \
  sh -c "npm install && npm run dev -- --host 0.0.0.0"
```

> `node_modules` はコンテナ内で生成されるが、ボリュームマウントによりホストの `viewer/node_modules` に
> 書かれる。プラットフォーム依存バイナリを避けるため、静的アダプタ (adapter-static) を採用している。

## 未実装 (今後)

- N世代ウィンドウの深さ調整 UI (祖先何代・子孫何代)。
- 全部盛りモードの切り替え UI (`fetchFullGraph` + `lod: true` は用意済み)。
- ノード詳細パネル。
