"""ダウンロード設定。

血統可視化に必要な蓄積系データ種別をまとめて指定する。
"""

# ソフトウェアID。JVInit に渡す。JRA-VAN 登録時に割り当てられた ID があればそれを使う。
# サンプルでは "UNKNOWN" だが、正式運用では自分の SoftwareID に置き換える。
SOFTWARE_ID = "UNKNOWN"

# 取得対象データ種別 (JVOpen の第1引数 dataspec)。
#
# 重要: dataspec に渡すのは「データ種別ID」で、これは【4桁固定】(複数指定は4の倍数桁)。
# 各レコード種別ID (UM/HN/SK/BT = 2桁) とは別物なので混同しないこと。
#
# JV-Data 仕様書「JVData データ種別一覧」より、必要なレコードの所属データ種別:
#   - UM 競走馬マスタ         -> DIFF (蓄積系ソフト用 蓄積情報)
#   - HN 繁殖馬マスタ         -> BLOD (蓄積系ソフト用 血統情報)
#   - SK 産駒マスタ           -> BLOD
#   - BT 系統情報             -> BLOD
# つまり血統情報 (HN/SK/BT) は DIFF ではなく BLOD にある。両方が必要なので
# データ種別IDを連結して "DIFFBLOD" (8桁 = 4の倍数) を JVOpen に渡す。
# 取得後、レコード先頭2バイトのレコード種別ID (UM/HN/SK/BT) でファイルに振り分ける。
#
# 注: DIFF/BLOD には他のレコード (RA/SE/オッズ/騎手/調教師 等) も含まれる。
#     血統可視化に不要なものは KEEP_RECORD_TYPES で除外する。
# 注: 2023-08-08 以降の10桁繁殖登録番号拡張データは "DIFN"/"BLDN" で提供される。
#     拡張データを使う場合は DATASPEC を "DIFNBLDN" に変更する。
DATASPEC = "DIFFBLOD"

# 出力対象とするレコード種別ID (先頭2バイト)。血統可視化に必要な4種のみ保存する。
# 空 set にすると全レコード種別を保存する。
KEEP_RECORD_TYPES = {"UM", "HN", "SK", "BT"}

# JVOpen の option 既定 (1=通常データ, 2=今週開催, 3=セットアップデータ)。
# 初回全件取得はセットアップ(3)。
DEFAULT_OPTION = 3

# 全期間取得を表す fromtime (YYYYMMDDhhmmss)。
FROMTIME_ALL = "00000000000000"

# JVGets のバッファサイズ (サンプルに準拠)。
BUFFER_SIZE = 110000

# 何レコードごとに gc.collect() を呼ぶか。
# win32com が JVGets のたびに溜め込む COM オブジェクトを定期回収し、メモリ枯渇を防ぐ。
GC_INTERVAL = 1000

# 生データの文字コード。JV-Data は cp932。
ENCODING = "cp932"
