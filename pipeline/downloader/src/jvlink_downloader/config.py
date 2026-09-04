"""ダウンロード設定。

血統可視化に必要な蓄積系データ種別をまとめて指定する。
"""

# ソフトウェアID。JVInit に渡す。JRA-VAN 登録時に割り当てられた ID があればそれを使う。
# サンプルでは "UNKNOWN" だが、正式運用では自分の SoftwareID に置き換える。
SOFTWARE_ID = "UNKNOWN"

# 取得対象データ種別 (JVOpen の第1引数「ファイル識別子」= dataspec)。
# 血統可視化に必要な4種を連結して1回の JVOpen でまとめて取得する。
#   UM: 競走馬マスタ / HN: 繁殖馬マスタ / SK: 産駒マスタ / BT: 系統情報
# 注: dataspec は種別コードの連結文字列。仕様書の「データ種別ID」に従う。
DATASPEC = "UMHNSKBT"

# JVOpen の option 既定 (1=通常データ, 2=今週開催, 3=セットアップデータ)。
# 初回全件取得はセットアップ(3)。
DEFAULT_OPTION = 3

# 全期間取得を表す fromtime (YYYYMMDDhhmmss)。
FROMTIME_ALL = "00000000000000"

# JVGets のバッファサイズ (サンプルに準拠)。
BUFFER_SIZE = 110000

# 生データの文字コード。JV-Data は cp932。
ENCODING = "cp932"
