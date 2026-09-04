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
#   - UM 競走馬マスタ / HN 繁殖馬マスタ / SK 産駒マスタ / BT 系統情報
#     これらはすべてデータ種別ID "DIFF" (蓄積系ソフト用 蓄積情報) に含まれる
#     (JV-Data 仕様書「JVData データ種別一覧」より)。
# したがって JVOpen には "DIFF" を渡す。取得後、レコード先頭2バイトの
# レコード種別ID (UM/HN/SK/BT ...) でファイルに振り分ける。
#
# 注: DIFF には血統以外のレコード (RA/SE/HR/オッズ 等) も多数含まれる。
#     血統可視化に不要なレコード種別は emit 側 (RecordWriter) で取捨選択する。
# 注: 2023-08-08 以降の繁殖登録番号10桁拡張データは "DIFN" で提供される。
#     セットアップ時に拡張データを使いたい場合は DATASPEC を "DIFN" に変更する。
DATASPEC = "DIFF"

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

# 生データの文字コード。JV-Data は cp932。
ENCODING = "cp932"
