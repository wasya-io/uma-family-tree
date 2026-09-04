# downloader — JV-Link 一括ダウンロード (Windows 専用)

JV-Link (JRA-VAN Data Lab.) から血統可視化に必要な蓄積系データをまとめて取得し、
生データファイルとして書き出す。**Windows でのみ動作する** (JV-Link は Windows の COM コンポーネントのため)。

出力した生データは、`pipeline` (Mac 等でも可) の入力 (`pipeline/input/`) として使う。

```
[Windows] downloader (JV-Link COM 経由でダウンロード)  ←ここ
   │  生データ (UM/HN/SK/BT ...) を出力
   ▼
[任意のOS] pipeline (DAG 化 → 配信 JSON 生成)
```

## 取得対象データ

血統可視化に必要な蓄積系レコード種別 (JV-Data 仕様書のデータ種別ID):

| レコード種別 | 内容 | 用途 |
|---|---|---|
| `UM` | 競走馬マスタ | 中心となる競走馬、3代血統 |
| `HN` | 繁殖馬マスタ | 親ポインタ (世代制限なしの遡行) |
| `SK` | 産駒マスタ | 3代血統の繁殖番号 |
| `BT` | 系統情報 | 系統による色分け |

`config.py` の `DATASPEC` でまとめて指定する (JVOpen の「ファイル識別子」)。

---

## 1. Python 実行環境の構築 (Windows / uv ベース)

Mac 側と同じく [uv](https://docs.astral.sh/uv/) で環境を統一する。Windows にはまだ Python が無い前提。

### 1-1. uv をインストール

PowerShell を開いて実行 (管理者権限は不要):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

インストール後、**PowerShell を開き直す** (PATH を反映するため)。確認:

```powershell
uv --version
```

### 1-2. 仮想環境を作成して依存を入れる

このリポジトリを Windows 機にも clone (または同期) し、`pipeline/downloader/` で:

```powershell
uv venv --python 3.11
uv pip install -e .
```

> `pipeline/downloader/pyproject.toml` は `pywin32` に依存する。
> `pywin32` は Windows でのみインストール可能 (COM 操作に必要)。

### 1-3. JV-Link のアーキテクチャ整合に関する注意

- 本 SDK は **64bit 版** (`JRA-VAN Data Lab. SDK Ver5.0.0_64bit`)。
  uv が入れる Python も 64bit なので基本は整合する。
- JV-Link 本体 (`JVDTLab.JVLink`) が正しく登録・利用者登録 (JVSetUIProperties での設定) 済みであること。
  未登録だと `JVInit` / `JVOpen` がエラーコードを返す。
- 初回は JV-Link の設定 (利用キー等) を済ませておく。設定 UI は
  `python -m jvlink_downloader.setup_ui` で開ける (JVSetUIProperties を呼ぶだけの補助)。

---

## 2. 使い方 (1 クリック実行)

`fetch.bat` をダブルクリックするだけ。内部で uv 経由の Python 取得スクリプトが走り、
`pipeline/input/` に生データを書き出す。

```
pipeline/downloader/fetch.bat
```

`fetch.bat` は以下と等価:

```powershell
uv run jvlink-fetch --out ..\input --fromtime 00000000000000
```

### オプション

| 引数 | 意味 | 既定 |
|---|---|---|
| `--out` | 生データ出力先 | `..\input` |
| `--fromtime` | 取得開始日時 (YYYYMMDDhhmmss)。空/0 は全期間 (セットアップ) | `00000000000000` |
| `--option` | JVOpen option (1=通常, 3=セットアップ) | `3` |
| `--dataspec` | 取得データ種別を上書き (既定は config.py の DATASPEC) | config 値 |

> 初回は `--option 3` (セットアップデータ) で全件取得、以降は `--option 1` + 前回の
> lastfiletime を `--fromtime` に渡して差分取得、という運用が一般的。

---

## 3. 現状

雛形。JV-Link API 呼び出し (JVInit/JVOpen/JVStatus/JVGets/JVClose) の流れは
SDK の Python サンプル (`Form1.py` / `Form2.py`) に準拠して実装済み。
実機 (JV-Link 登録済み Windows) での疎通確認は未実施 (この開発環境は Mac のため)。
