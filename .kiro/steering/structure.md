# リポジトリ構成 (モノレポ)

> ⚠️ 注: 本ファイルの「データフロー」「役割分担」の一部は **初期の R2 + 静的 JSON 構成**の記述で、
> 現行は **Cloudflare D1 + Pages Functions** に移行済み。現行のデータモデルは `docs/data-model.md`、
> 運用・デプロイ・無料枠の注意は `.kiro/steering/operations.md` を参照。
> (ディレクトリ構成・命名規約の記述は現行でも有効。)

```
uma-family-tree/
├─ .kiro/
│  └─ steering/            # プロダクト・技術・構成の常時参照ドキュメント
├─ .refarence/             # JV-Link SDK 資料・サンプル (参照用、加工には非依存で扱う)
├─ pipeline/               # データ加工パイプライン (Python)
│  ├─ src/
│  ├─ input/               # JV-Link がダンプした生データの配置先 (gitignore 推奨)
│  ├─ output/              # 生成した JSON 群の出力先 (gitignore 推奨)
│  ├─ pyproject.toml
│  └─ README.md
├─ viewer/                 # ビューア (SvelteKit + 3d-force-graph)
│  ├─ src/
│  ├─ static/              # 全部盛り専用ファイルなど、少数の静的データはここも可
│  ├─ package.json
│  └─ README.md
└─ README.md               # モノレポ全体の説明
```

## 役割分担

- **pipeline/**: Windows マシンで JV-Link が出力した生データ (UM/HN/SK/BT マスタ) を入力に取り、
  DAG 化して配信用 JSON 群を生成する。生成物は R2 にアップロードする (または全部盛りは viewer/static)。
- **viewer/**: R2 から JSON を fetch して 3D 描画する。組み立てロジックは持たない。

## データフロー

```
[Windows] JV-Link ダンプ
   │  (生データファイル: UM/HN/SK/BT マスタ)
   ▼
[pipeline] Python 加工 (DAG 構築 → 分割 JSON 生成)
   │
   ├─ horses/{KettoNum}.json      馬ノードファイル (祖先M代+子孫L代を事前展開)
   ├─ search-index.json           検索辞書 (カナ/英字 → KettoNum)
   ├─ keito-master.json           系統マスタ (KeitoId → 系統名+色、主要系統に丸め)
   └─ full/{KettoNum}.json        全部盛り専用ファイル (限定始祖の全子孫)
   ▼
[R2] data.<独自ドメイン> で配信 (CORS 設定)
   ▼
[Cloudflare Pages] viewer が fetch して描画
```

## 命名・キー規約

- 馬の一意キーは `KettoNum` (血統登録番号、10桁)。ファイル名・URL 共有パラメータもこれを基準にする。
- URL 共有: `/?horse={KettoNum}`。
- 配信ベース URL はビューアの環境変数 `PUBLIC_DATA_BASE_URL` で持つ (r2.dev 暫定 → 本番サブドメインの差し替えを容易に)。
