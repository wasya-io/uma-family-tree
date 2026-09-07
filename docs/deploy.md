# 本番デプロイ手順 (Cloudflare Pages + D1)

viewer を Cloudflare Pages に、血統データを Cloudflare D1 (SQLite) にデプロイする手順。

構成:

```
[pipeline] SQL 生成 (pedigree.sql)
     │  wrangler d1 execute --remote
     ▼
[Cloudflare D1] uma-family-tree  ← horses / edges / keito_master / meta
     ▲  D1 バインディング (DB)
     │
[Cloudflare Pages] viewer (SvelteKit + Pages Functions API)
     │  独自ドメイン
     ▼
   利用者
```

> ⚠️ **認証が必要な操作はあなた (リポジトリ所有者) が実行する必要があります。**
> Kiro (エージェント) からは `wrangler login` / `d1 create` / `--remote` 投入 / `pages deploy` /
> ドメイン割当は実行できません。以下、🧑 マークの付いた手順が手動実行対象です。

---

## 0. 前提 / 環境

- Node は Volta 経由 (このマシンではホストに直接入っていない):

  ```bash
  export VOLTA_HOME="$HOME/.volta"
  export PATH="$VOLTA_HOME/bin:$PATH"
  node -v   # v20.x
  ```

- wrangler は `viewer` の devDependency。`viewer/` で `./node_modules/.bin/wrangler` を使う。
- 以降のコマンドは特記なき限り **cwd = `viewer/`**。

---

## 1. 🧑 Cloudflare にログイン

```bash
cd viewer
export VOLTA_HOME="$HOME/.volta" && export PATH="$VOLTA_HOME/bin:$PATH"
./node_modules/.bin/wrangler login
```

ブラウザが開くので Cloudflare アカウントで承認する。

確認:

```bash
./node_modules/.bin/wrangler whoami
```

---

## 2. 🧑 本番 D1 データベースを作成

```bash
./node_modules/.bin/wrangler d1 create uma-family-tree
```

出力される `database_id` (UUID) を控える。例:

```
[[d1_databases]]
binding = "DB"
database_name = "uma-family-tree"
database_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   ← これ
```

---

## 3. wrangler.toml の database_id を差し替え

`viewer/wrangler.toml` の `database_id` を、手順 2 で得た実 ID に置き換える。

```toml
[[d1_databases]]
binding = "DB"
database_name = "uma-family-tree"
database_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # 実 ID
```

> ⚠️ ローカル開発では `local-dev-placeholder-...` のままで動いていた。実 ID に変えても
> `--local` はローカル SQLite を使い続けるので、ローカル開発には影響しない。
> **この差し替えはコミットしてよい** (database_id は秘密情報ではない)。

---

## 4. 投入用 SQL を最新化 (データ更新時のみ)

生データ (`pipeline/input/`) を更新した場合のみ、SQL を作り直す。初回は既存の
`viewer/db/pedigree.sql` をそのまま使ってよい。

```bash
# cwd = pipeline
.venv/bin/uma-pipeline --input ./input --output ./output
cp output/pedigree.sql ../viewer/db/pedigree.sql
```

生成物の規模 (参考): horses 153,798 / edges 282,676 / keito 21 / meta 1、約 27MB。

---

## 5. 🧑 本番 D1 にスキーマとデータを投入

よく使う操作は `viewer/package.json` の npm スクリプトにしてある
(`export VOLTA_HOME=... && export PATH=...` を通したうえで実行):

| スクリプト | 内容 |
|---|---|
| `npm run db:schema:remote` | 本番 D1 にスキーマ投入 |
| `npm run db:load:remote` | 本番 D1 にデータ投入 (pedigree.sql) |
| `npm run db:schema:local` / `db:load:local` | ローカル D1 へ (動作確認用) |

### 5-1. スキーマ

```bash
# cwd = viewer
npm run db:schema:remote
```

### 5-2. データ

```bash
npm run db:load:remote
```

> ⚠️ **大きな SQL の投入について**
> `pedigree.sql` は約 27MB / 2,185 文。D1 の制約は「1 SQL 文あたり最大 100KB」で、
> 本 SQL の最長文は約 28.7KB なので**文単位では上限内**。
>
> ⚠️ **トランザクション文は使わない。** Cloudflare D1 (remote) は SQL の
> `BEGIN TRANSACTION` / `COMMIT` / `SAVEPOINT` を受け付けない
> (`To execute a transaction, please use ...` エラーになる)。pipeline の emit は
> これらを出力しないよう修正済み。手書きで SQL を足す場合もトランザクション制御文は入れないこと。
>
> `wrangler d1 execute --file` は巨大ファイルで不安定という報告もある
> ([workers-sdk#4407](https://github.com/cloudflare/workers-sdk/issues/4407),
> [#9503](https://github.com/cloudflare/workers-sdk/issues/9503))。
> 失敗したら **手順 5-3 の分割投入**にフォールバックする。

### 5-3. (フォールバック) 分割投入

`pedigree.sql` を小さな塊 (100 文ごと) に分割して順に投入する。分割スクリプトを用意してある
(各チャンクにトランザクション制御文は付けない):

```bash
# cwd = viewer
./db/split-and-import.sh remote     # 本番 D1 へ分割投入
./db/split-and-import.sh local      # ローカル D1 へ (動作確認用)
```

### 5-4. 投入確認

```bash
./node_modules/.bin/wrangler d1 execute uma-family-tree --remote \
  --command="SELECT (SELECT COUNT(*) FROM horses) AS horses, (SELECT COUNT(*) FROM edges) AS edges, (SELECT COUNT(*) FROM keito_master) AS keito, (SELECT value FROM meta WHERE key='data_timestamp') AS ts;"
```

`horses=153798 / edges=282676 / keito=21 / ts=20230731144210` 相当が返れば OK。

---

## 6. ビルド + デプロイ

このプロジェクトは **CLI (`wrangler pages deploy`) デプロイを正とする**。CLI デプロイは
`wrangler.toml` の `[[d1_databases]]` を読んで D1 バインディングを自動で紐付けるため、
ダッシュボードでの手動バインディング設定が不要になる (Git 連携より確実)。

```bash
# cwd = viewer
export VOLTA_HOME="$HOME/.volta" && export PATH="$VOLTA_HOME/bin:$PATH"
npm run check          # 型チェック (0 errors) ※任意
npm run build:deploy   # 🧑 ビルド → Pages デプロイを一括実行
```

- `npm run build:deploy` = `npm run build`(`.svelte-kit/cloudflare` 出力)+ `npm run deploy`。
  **ビルド忘れを防ぐため、通常はこれ一つを使う。**
- ビルドだけ / デプロイだけを個別にやりたい場合は `npm run build` / `npm run deploy`。
- 初回デプロイ時はプロジェクト作成の確認が入る。production ブランチは `main` を選ぶ。

> Git 連携 (自動デプロイ) は**採用しない**。もし将来使う場合は、ダッシュボードで
> ルートディレクトリ=`viewer` / フレームワークプリセット=SvelteKit /
> ビルドコマンド=`npm run build` / 出力ディレクトリ=`.svelte-kit/cloudflare` を設定し、
> **さらに手順 7 の D1 バインディングをダッシュボードで手動設定する必要がある**。

---

## 7. D1 バインディングの確認

CLI (`wrangler pages deploy`) デプロイなら `wrangler.toml` の `[[d1_databases]]` が
自動で紐付くため、通常は**追加設定不要**。デプロイ後に API を叩いて確認する
(`<pages-url>` は払い出された URL):

```bash
curl -s "https://<pages-url>/api/meta"                                        # {"data_timestamp":"..."}
curl -s -o /dev/null -w "%{http_code}\n" "https://<pages-url>/api/horse/H11202369"   # 200
```

`/api/meta` が値を返し `/api/horse/...` が 200 なら D1 は正しく繋がっている。

もし API が 500 (DB undefined) になる場合のみ、ダッシュボードで手動バインディングする:
Cloudflare ダッシュボード → Workers & Pages → uma-family-tree → Settings → Functions →
D1 database bindings:

- Variable name: `DB`
- D1 database: `uma-family-tree`

を production / preview 両方に設定し、再デプロイする。

---

## 8. 🧑 独自ドメインの割当

Cloudflare ダッシュボード → uma-family-tree → Custom domains → Set up a custom domain →
所有ドメインのサブドメイン (例 `uma.example.com`) を割り当てる。DNS は Cloudflare 管理下なら
自動で CNAME が張られる。

割当後、`https://uma.example.com/?horse=H11202369` で表示を確認する。

---

## 9. rows_read の実測 (無料枠見積もりの確定)

ローカル D1 は `rows_read` を返さないため、本番でのみ計測できる。代表的な馬を数件開いた後、
ダッシュボード → uma-family-tree (D1) → Metrics で rows read / rows written を確認する。

想定: 通常表示は再帰 CTE + 両方向インデックスで 1 リクエストあたり数百〜数千行程度。
D1 無料枠は 1 日あたり読み取り 500 万行・書き込み 10 万行 (2026 時点の目安、最新は
[D1 Pricing](https://developers.cloudflare.com/d1/platform/pricing/) を参照)。
API レスポンスに `Cache-Control` を付与済み (horse=5分, keito=1日) なので、
同一馬の連続アクセスは Cloudflare キャッシュで D1 に到達せず、実クエリ数は抑えられる。

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| `To execute a transaction, please use ...` | SQL に `BEGIN TRANSACTION`/`COMMIT` が混入。remote D1 は非対応。emit は除去済み。手書き SQL でも入れない |
| `d1 execute --remote --file` が巨大 SQL で失敗 | 手順 5-3 の分割投入 (`./db/split-and-import.sh remote`) に切替 |
| API が 500 (D1 バインド未設定) | 手順 7 のバインディング確認。CLI デプロイなら通常自動で紐付く |
| API が 500 (バインドパラメータ超過) | IN 句に数百 id を渡していないか確認。pedigree.ts は再帰 CTE を JOIN してバインドを 3 個に固定済み |
| デプロイ後も古い挙動 | ビルド忘れの可能性。`npm run build:deploy` で再デプロイ |
| 独自ドメインが 522/525 | DNS 伝播待ち。数分〜。Cloudflare 管理下ドメインなら通常自動 |
