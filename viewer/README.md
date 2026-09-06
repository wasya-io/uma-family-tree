# viewer — 3D 血統ビューア

SvelteKit + [3d-force-graph](https://github.com/vasturiano/3d-force-graph) で血統 DAG を 3D 表示する
Cloudflare Pages 向けフロントエンド。データは **Cloudflare D1 (SQLite)** に置き、
**Pages Functions API** (`/api/*`) 経由で取得する。血統の探索 (祖先/子孫) は D1 上の再帰 CTE で行い、
組み立て処理はビューアに持たせない。

## セットアップ (ローカル開発)

```bash
# Node は Volta 経由 (このマシンではホストに直接入っていない)
export VOLTA_HOME="$HOME/.volta" && export PATH="$VOLTA_HOME/bin:$PATH"

npm install

# ローカル D1 にスキーマとデータを投入 (初回のみ)
./node_modules/.bin/wrangler d1 execute uma-family-tree --local --file=./db/schema.sql
./node_modules/.bin/wrangler d1 execute uma-family-tree --local --file=./db/pedigree.sql

# ビルドしてローカル Pages (Functions + D1 バインディング) を起動
npm run build
./node_modules/.bin/wrangler pages dev .svelte-kit/cloudflare --port 5173 --ip 0.0.0.0
```

`http://localhost:5173/?horse=H11202369` で実データ版が動く。

> 注: `db/pedigree.sql` は pipeline の生成物 (約 27MB、gitignore 済み)。
> `pipeline/` で `uma-pipeline` を実行して生成し、`viewer/db/` にコピーする。
> ビルド後に再ビルドした場合は `wrangler pages dev` を再起動しないと新しい Functions を掴まない。

## データ層 (D1)

| テーブル | 役割 |
|---|---|
| `horses` | 馬ノード (id="H"+繁殖番号、名前/カナ/性別/毛色/生年/系統ID) |
| `edges` | 親子エッジ (parent_id → child_id, parent='father'\|'mother') |
| `keito_master` | 系統マスタ (色分け) |
| `meta` | メタ情報 (`data_timestamp` = データ基準時点) |

インデックス: `edges(child_id)` / `edges(parent_id)` (双方向探索)、`horses(kana/name/ketto_num)` (検索)。

## API (Pages Functions)

| エンドポイント | 役割 |
|---|---|
| `GET /api/horse/[id]?anc=&desc=&full=` | 中心馬 + 祖先/子孫 (再帰CTE)。`full=1` で子の代表絞りを解除。cache 5分 |
| `GET /api/search?q=` | カナ/名前/血統番号の LIKE 検索 (20件) |
| `GET /api/keito` | 系統マスタ。cache 1日 |
| `GET /api/exists/[id]` | 馬の存在確認 (中心切替ボタンの活性判定) |
| `GET /api/meta` | メタ情報 (データ基準時点) |

## 構成

| ファイル | 役割 |
|---|---|
| `src/lib/types.ts` | データ契約 (API レスポンスと対応) |
| `src/lib/data.ts` | `/api/*` の fetch クライアント |
| `src/lib/server/pedigree.ts` | D1 再帰 CTE による祖先/子孫探索 (バインドを 3 個に固定) |
| `src/lib/graph.ts` | 3d-force-graph ラッパ (色分け・父母リンク・中心強調・ラベルフェード) |
| `src/lib/HorseSearch.svelte` | カナ/英字インクリメンタルサーチ (サーバ側検索) |
| `src/routes/+page.svelte` | メイン画面 (グラフ + 検索 + 詳細パネル + URL 同期 `?horse=`) |
| `db/schema.sql` | D1 スキーマ |
| `db/split-and-import.sh` | 巨大 SQL を分割して D1 投入するフォールバック |

## 機能

- 系統 (keitoId) によるノード色分け。中心馬は原点固定 + ラベル明滅で強調。
- リンク: 父方=青の細線 / 母方=赤の太線 + 流れる粒子 (3D では破線が扱えないため色・太さ・粒子で区別)。
- 祖先=上 (+Y) / 子孫=下 (−Y) にレイアウト。ドラッグ回転の中心は中心馬 (原点) に一致。
- ノードタップで詳細パネル → 「中心にする」で再センタリング (URL `?horse=` を更新 → 共有可能)。
- 直仔が多い馬は代表的な子のみ表示 + 「すべて表示」トグル (集合体感を緩和)。
- ラベルフェード (世代 + カメラ距離)。中心/選択は常時濃い。
- 検索: カナ + 名前 + 血統番号のサーバ側インクリメンタルサーチ。
- フッターにデータ基準時点を表示 (meta テーブルの `data_timestamp`)。

## デプロイ (Cloudflare Pages + D1)

本番デプロイの詳細手順は **[`../docs/deploy.md`](../docs/deploy.md)** を参照。要点:

- `@sveltejs/adapter-cloudflare` で Pages Functions 込みの出力を生成 (`.svelte-kit/cloudflare`)。
- 血統データは Cloudflare D1 に投入し、Pages に D1 バインディング (`DB`) を紐付ける。
- `wrangler.toml` の `database_id` を本番 D1 の実 ID に差し替える (初期値はローカル用プレースホルダ)。
- ビルド `npm run build` → `wrangler pages deploy .svelte-kit/cloudflare`。
- 巨大 SQL の投入が失敗する場合は `db/split-and-import.sh remote` で分割投入。

## 未実装 (今後)

- N世代ウィンドウの深さ調整 UI (祖先何代・子孫何代)。
- 全部盛りモード (固定 JSON ベースを検討中、優先度低)。
