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

血統可視化に必要な**レコード種別** (レコード先頭2バイトの ID):

| レコード種別ID | 内容 | 用途 |
|---|---|---|
| `UM` | 競走馬マスタ | 中心となる競走馬、3代血統 |
| `HN` | 繁殖馬マスタ | 親ポインタ (世代制限なしの遡行) |
| `SK` | 産駒マスタ | 3代血統の繁殖番号 |
| `BT` | 系統情報 | 系統による色分け |

### dataspec とレコード種別の関係 (重要)

JVOpen に渡す **dataspec は「データ種別ID」で 4 桁固定**。上記の `UM`/`HN`/`SK`/`BT` は
「レコード種別ID」(2桁) であり、dataspec に渡すものとは**別物**。

JV-Data 仕様書「JVData データ種別一覧」より、必要なレコードの所属データ種別は分かれている:

| レコード種別 | 所属データ種別ID |
|---|---|
| UM 競走馬マスタ | `DIFF` (蓄積系ソフト用 蓄積情報) |
| HN 繁殖馬マスタ | `BLOD` (蓄積系ソフト用 **血統情報**) |
| SK 産駒マスタ | `BLOD` |
| BT 系統情報 | `BLOD` |

血統情報 (HN/SK/BT) は `DIFF` ではなく `BLOD` にある。よって JVOpen には両方を連結した
**`"DIFFBLOD"`** (8桁 = 4の倍数) を渡す。取得後、各レコードの先頭2バイト (レコード種別ID) で
`UM.dat` / `HN.dat` / `SK.dat` / `BT.dat` に振り分け、不要レコードは `config.KEEP_RECORD_TYPES`
で除外する。

> - `"UMHNSKBT"` のようにレコード種別IDを連結すると `JVOpen -111` (dataspec 不正) になる。
> - `"DIFF"` だけだと UM しか取れず HN/SK/BT が欠ける (血統情報は BLOD のため)。
> - 2023-08-08 以降の10桁繁殖登録番号拡張データは `"DIFNBLDN"` で提供される。

`config.py` の `DATASPEC`(既定 `"DIFFBLOD"`)で指定する。

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

### 1-3b. COM バインディングについて (早期バインディング)

本ツールは JVGets の out 引数を安定して扱うため、**早期バインディング**
(`win32com.client.gencache.EnsureDispatch`) を使う。初回呼び出し時に JV-Link の
タイプライブラリから型情報つきのキャッシュ (gen_py) が生成される。

- もし `AttributeError` や生成キャッシュ絡みの不具合が出たら、gen_py キャッシュを削除して
  再実行するとよい (次回自動再生成される):

  ```powershell
  # 例: ユーザーごとの gen_py キャッシュ場所
  Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Temp\gen_py"
  ```

- 早期バインディングに失敗した場合は自動的に遅延バインディング (Dispatch) に
  フォールバックする (安定性は落ちる)。

### 1-3. JV-Link のアーキテクチャ整合に関する注意

- 本 SDK は **64bit 版** (`JRA-VAN Data Lab. SDK Ver5.0.0_64bit`)。
  uv が入れる Python も 64bit なので基本は整合する。
- JV-Link 本体 (`JVDTLab.JVLink`) が正しく登録・利用者登録 (JVSetUIProperties での設定) 済みであること。
  未登録だと `JVInit` / `JVOpen` がエラーコードを返す。
- 初回は JV-Link の設定 (利用キー等) を済ませておく。設定 UI は
  `uv run jvlink-setup` で開ける (JVSetUIProperties を呼ぶだけの補助)。

### 1-4. 利用キー (サービスキー) の設定 ★初回必須

JRA-VAN の**利用キー (17桁の英数字)** が未設定だと、`JVOpen` が `-1` (該当データなし) を返し
データを取得できない。入手した利用キーを設定する。方法は 2 通り:

- コマンドで設定 (確実):

  ```powershell
  uv run jvlink-setkey <17桁の利用キー>
  ```

  戻り値 0 で成功。-100 は値が不正、または既に設定済みで変更不可。

- 設定 UI から入力:

  ```powershell
  uv run jvlink-setup
  ```

  ダイアログの利用キー入力欄に貼り付けて保存する。

> 利用キーはレジストリに保存され、以降の `JVInit` / `JVOpen` で使われる。
> **利用キーはコードや Git にコミットしないこと** (個人の認証情報)。

---

## 2. 使い方 (1 クリック実行)

`setup.bat` をダブルクリックするだけ。内部で `DIFF` と `BLOD` を **別々のプロセス**で
順に取得し、`pipeline/input/` に生データを書き出す。

```
pipeline/downloader/setup.bat
```

`setup.bat` は以下と等価:

```powershell
uv run jvlink-fetch --out ..\input --dataspec DIFF --fromtime 00000000000000 --option 4
uv run jvlink-fetch --out ..\input --dataspec BLOD --fromtime 00000000000000 --option 4
```

### なぜ DIFF と BLOD を分けるのか (メモリ対策)

`DIFFBLOD` を 1 プロセスで一括取得すると、win32com が JVGets 呼び出しごとに COM
オブジェクトを溜め込み、フル・セットアップ (数百万レコード) の途中で `MemoryError`
になる (実機で 524 ファイル中 244 ファイル目付近で発生を確認)。

対策:
- **データ種別を 2 プロセスに分割**する。プロセスが終了すれば OS が COM メモリを完全に
  回収するため、次のプロセスはクリーンな状態で始められる。
- 各プロセス内でも `config.GC_INTERVAL` 件ごとに `gc.collect()` を呼び、蓄積を抑える。

> それでも BLOD 単独で落ちる場合は、`--fromtime` に期間を指定して取得を分割する
> (例: 年ごと)。その際は 2 回目以降に `--append` を付けて既存 .dat に継ぎ足す。

#### BLOD が 1 プロセスで完走しない場合: 期間分割バッチ

実機で BLOD を 1 プロセス取得すると、300〜365 ファイル付近で COM メモリ蓄積により
OS ごと重くなる/フリーズすることを確認。対策として **期間で分割し、各期間を別プロセス**
で取得する `setup_blod_split.bat` を用意した。

```
pipeline/downloader/setup_blod_split.bat
```

- `option=4` (セットアップ・ダイアログ無し) + `fromtime="開始-終了"` の期間指定で、
  1986〜現在を数年刻みに分割。
  - 注: `option=1` (通常/差分データ) はセットアップ直後だと差分が無く `-1` (該当なし) になる。
    過去の全データはセットアップ用データにしか無いため、historical 取得は option=4 が必須。
    仕様書より option=3/4 でも fromtime の "開始-終了" 期間指定は有効。
- 1 チャンク目は上書き、以降は `--append` で `HN.dat`/`SK.dat`/`BT.dat` に継ぎ足す。
- 各チャンクは別プロセスなので、終了ごとに OS が COM メモリを完全回収する。
- 途中のチャンクで失敗しても、完了済みチャンクのデータは残る。失敗チャンクの期間を
  さらに細かく割って再実行すればよい。

> 期間分割で同一マスタが重複する可能性はあるが、pipeline 側はレコードを
> KettoNum / HansyokuNum でキー付けするため、重複は上書きされ実害はない。

DIFF (UM) は 1 プロセスで完走するため `setup.bat` の DIFF 部分をそのまま使う。
つまり運用は「`setup.bat` の DIFF で UM → `setup_blod_split.bat` で HN/SK/BT」となる。

### オプション

| 引数 | 意味 | 既定 |
|---|---|---|
| `--out` | 生データ出力先 | `..\input` |
| `--dataspec` | 取得データ種別 (4桁×n)。`DIFF` / `BLOD` を個別指定推奨 | config 値 (`DIFFBLOD`) |
| `--fromtime` | 取得開始日時 (YYYYMMDDhhmmss)。0 は全期間 | `00000000000000` |
| `--option` | JVOpen option (1=通常, 3/4=セットアップ) | `3` |
| `--append` | 既存 .dat に追記 (既定は上書き) | off |

> 初回は `--option 4` (ダイアログ無しセットアップ) で全件取得、以降は `--option 1` +
> 前回の `lastfiletime.txt` の値を `--fromtime` に渡して差分取得、という運用が一般的。

---

## 3. 現状

JV-Link API 呼び出し (JVInit/JVOpen/JVStatus/JVGets/JVClose) の流れは SDK の Python
サンプル (`Form1.py` / `Form2.py`) に準拠。DIFF (UM) の取得は実機で成功を確認済み。
BLOD (HN/SK/BT) を含むフル取得は、win32com のメモリ蓄積対策として **DIFF/BLOD を
分割実行**する方式に変更した (実機での完走確認は継続中)。
