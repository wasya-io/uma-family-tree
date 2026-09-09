# 運用・デプロイの要点と再発防止 (viewer / Cloudflare)

viewer を Cloudflare Pages + D1 で運用する上での、**実際にハマった問題と対策**の記録。
デプロイや Cloudflare 周りを触る前に必ず読むこと。詳細手順は `docs/deploy.md`、
データモデルは `docs/data-model.md`、機能は `docs/features.md`。

## 構成 (現行)

- 配信: **Cloudflare Pages** + **Pages Functions**(`/api/*`)。データは **Cloudflare D1 (SQLite)**。
  (初期の R2 + 静的 JSON 構成からは移行済み。`.kiro/steering/structure.md` の R2 記述は旧仕様。)
- ビルド: SvelteKit + `@sveltejs/adapter-cloudflare`(出力 `.svelte-kit/cloudflare`、`_worker.js` 方式)。
- デプロイ: **元プロジェクト `uma-family-tree`** に対する **Git 連携ビルド**(`main` push で自動)。
  本番 URL は `https://uma-family-tree.pages.dev`。
- D1: `uma-family-tree`(Pages とは独立。Pages を消しても D1 は残る)。

## ⚠️ 無料枠の1日上限 (最重要・今回の全404の真因)

Cloudflare 無料プランには **1日ごとの上限**があり、超えると**その日のあいだ機能が停止**する。
**UTC 0時 (日本 朝9時) にリセット**される。

- **Workers/Pages Functions リクエスト: 10万/日**
  - 超過すると **全 Functions が実行されず、全ルートが 404**(過去の正常デプロイも一斉に 404 になる)。
    Functions が動かないので tail ログにも何も出ない。**コードやデプロイの問題と誤認しやすい**。
  - 確認場所: ダッシュボード右上アカウント → **使用量 (Usage)** の「今日のリクエスト N / 100,000」。
- **D1 Rows read: 500万/日**
  - 超過すると D1 クエリが拒否され、`/api/horse` `/api/search` 等が **500**(行を読むもののみ)。
    `SELECT 1` など行を読まないクエリは通るので誤判定に注意。**必ず `COUNT(*)` 等で確認**。
  - エラー: `exceeded D1's free tier daily row read limit [code: 7500]`。

### 切り分けの鉄則

**「全ルート404」または「行を読む API だけ500」が出たら、まず使用量ダッシュボードで無料枠を疑う。**
過去の正常デプロイまで404なら、ほぼ確実にアカウント側の上限超過。コードを疑う前にここを見る。

### 上限を使い切らない運用

- **動作確認は最小限のリクエストに絞る**(各エンドポイント1回程度)。デバッグ時の多数の curl / 再デプロイ後の
  一括確認が積み上がって上限に達する。今回はまさに調査アクセスで 13.4万リクエストに達した。
- SPA は初回表示で複数 API を叩く。ブラウザ更新の連打も消費する。
- **再発防止の実装済み対策**:
  - `/api/*` を Cache API (`caches.default`, `viewer/src/lib/server/cache.ts` の `withEdgeCache`) で
    エッジキャッシュ。同一 URL の再アクセスは Functions を実行せずキャッシュから返る。
  - 子孫 fanout を相関サブクエリ化し、全 edges スキャンを廃止して rows_read を削減 (`pedigree.ts`)。

## ⚠️ wrangler のバージョン

- **wrangler は v3 系に固定 (`3.114.17`)**。`package.json` で固定済み。
- **v4 は使わない**。v4 は Pages を「Workers static assets」方式で扱い、adapter-cloudflare の
  `_routes.json` を無視して**全リクエストを Worker 送りにする**ため、静的アセット (`/_app/*.js`) が
  404 になりサイト全体が壊れる(ローカル `pages dev` で "Ignoring provided _routes.json" 警告が出る)。

## ⚠️ compatibility flags

- `wrangler.toml` に `compatibility_flags = ["nodejs_compat"]` を入れてある
  (`_worker.js` が `node:async_hooks` 等 Node 組み込みを参照するため)。
- **Git 連携 / CLI デプロイでは wrangler.toml のフラグ・D1 バインディングが本番に反映されないことがある。**
  Cloudflare ダッシュボード → プロジェクト → **Settings → Runtime** の互換性フラグ、
  **Settings → Bindings** の D1 (`DB` = `uma-family-tree`) を、**Production / Preview 両方**に設定しておく。

## Git 連携ビルドの設定 (ダッシュボード)

- Production branch: `main`
- フレームワークプリセット: SvelteKit
- ビルドコマンド: `npm run build`
- ビルド出力ディレクトリ: `.svelte-kit/cloudflare`
- **ルートディレクトリ: `viewer`**(モノレポなので必須)
- ビルド環境の Node は `viewer/.node-version`(20.20.2)で固定。

## データ更新時の注意

- スキーマ変更(列追加など)を伴う場合、D1 は `CREATE TABLE IF NOT EXISTS` では反映されない。
  **DROP TABLE → schema → data の順**で作り直す(手順は `docs/deploy.md`)。
- remote D1 は SQL の `BEGIN TRANSACTION` / `COMMIT` / `SAVEPOINT` を受け付けない
  (pipeline の emit は出力しない)。
- データ更新後はエッジキャッシュ (s-maxage 最大7日) に古い応答が残りうる。必要ならダッシュボードで
  キャッシュパージ、または再デプロイで更新する。

## データ再取得 (downloader / Windows) の注意

生データの再取得は `pipeline/downloader/`(Windows + JV-Link)で行う。実運用でハマった点:

- **JV-Link の取得オプション**: option=1 では「新しいデータが無い」と返ることがある。マスタ一括取得は
  option=4 系を使う(取得区分は用途で変わる。詳細は downloader/README とコード)。
- **一括取得は極めて重い**: フル・セットアップは数百万レコードに及び、素朴に回すと **OS ごとフリーズ**
  したり **MemoryError** で落ちる(300〜500ファイル台で頻発した)。→ **分割バッチ方式**で取得する
  (`setup_blod_split.bat` 等)。
- **メモリ対策 (実装済み・崩さない)**: `fetch.py` の JVGets ループは、入力バッファをループ外で1回だけ確保して
  使い回し、`memoryview` はコピー直後に解放する。これを怠ると COM 側 SAFEARRAY が溜まりメモリ枯渇する。
- **JVGets の戻り値は環境で揺れる**: データが `memview` に入る場合と、入力バッファ `buff` 側に入る場合が
  ある。`_extract_record` が両対応している(`NoneType is not subscriptable` 系のエラーはこの揺れが原因)。
- **保持レコードを絞る**: 血統可視化に必要なのは UM/HN/SK/BT のみ。RA/SE/オッズ等は取得段階で捨てる
  (`config.KEEP_RECORD_TYPES`)。将来「重賞勝ち」対応で RA/SE が必要になったらここを広げる。
- 取得後は `lastfiletime.txt`(データ基準時点)も一緒に `pipeline/input/` へ。これが meta の
  `data_timestamp` になり、フッターと免責の日付に使われる。

## ローカル開発の罠

- `wrangler pages dev` は build 後に**再起動しないと新 worker を掴まない**。
- レスポンスの `Cache-Control` により `.wrangler/state/v3/cache` に古い応答が残る。
  挙動が変わらないときは `.wrangler/state/v3/cache` を削除して再起動。
- ブラウザは Cmd+Shift+R / DevTools の Disable cache を使う。
- ローカル D1 は database_id ごとに状態ディレクトリが分かれる。id を変えると空 DB になり
  再投入が必要 (`npm run db:schema:local` → `db:load:local`)。
