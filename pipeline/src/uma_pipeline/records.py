"""JV-Data レコードのパース。

対象レコード (`.refarence/.../JV-Data構造体/Python版/JVData_Struct.py` の構造体に対応):

- UM (JV_UM_UMA)       競走馬マスタ   … KettoNum, 馬名/カナ/英字, 性別, 毛色, 生年月日, 3代血統
- HN (JV_HN_HANSYOKU)  繁殖馬マスタ   … HansyokuNum, KettoNum, 親ポインタ(F/M), 馬名, 性別, 毛色, 生年
- SK (JV_SK_SANKU)     産駒マスタ     … KettoNum, 3代血統の繁殖番号
- BT (JV_BT_KEITO)     系統情報       … HansyokuNum, KeitoId, KeitoName

JV-Data は各レコードが固定長バイト列で、レコード種別ID (先頭2バイト) で識別される。
本モジュールは「生データファイル群 → 種別ごとのレコード dataclass 列」への変換を担う。

TODO: 実際の生データファイルの形式 (JV-Link のダンプ形式) を確認して読み込みを実装する。
      オフセット/バイト長は JVData_Struct.py の SetDataB を参照して定義する。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UmaRecord:
    """競走馬マスタ (UM) の血統可視化に必要な部分。"""

    ketto_num: str                     # 血統登録番号 (10桁) — ノード一意キー
    name: str = ""                     # 馬名
    kana: str = ""                     # 馬名半角カナ
    eng: str = ""                      # 馬名欧字
    sex_cd: str = ""                   # 性別コード
    keiro_cd: str = ""                 # 毛色コード
    birth_year: int | None = None      # 生年 (生年月日から)
    # 3代血統情報 (14頭ぶんの繁殖登録番号)。UM 単体で3代までは辿れる。
    ketto3_hansyoku_nums: list[str] = field(default_factory=list)


@dataclass
class HansyokuRecord:
    """繁殖馬マスタ (HN)。親ポインタを持つため、世代制限なしの遡行の要。"""

    hansyoku_num: str                  # 繁殖登録番号 (10桁)
    ketto_num: str = ""                # 血統登録番号 (競走馬としても登録されていれば)
    name: str = ""
    kana: str = ""
    eng: str = ""
    sex_cd: str = ""
    keiro_cd: str = ""
    birth_year: int | None = None
    father_hansyoku_num: str = ""      # 父馬繁殖登録番号 (HansyokuFNum)
    mother_hansyoku_num: str = ""      # 母馬繁殖登録番号 (HansyokuMNum)


@dataclass
class KeitoRecord:
    """系統情報 (BT)。HansyokuNum → 系統。"""

    hansyoku_num: str
    keito_id: str = ""                 # 系統ID (色分けキー)
    keito_name: str = ""               # 系統名


@dataclass
class ParsedData:
    """パース結果の集約。graph 構築の入力になる。"""

    uma: dict[str, UmaRecord] = field(default_factory=dict)          # key: ketto_num
    hansyoku: dict[str, HansyokuRecord] = field(default_factory=dict)  # key: hansyoku_num
    keito: dict[str, KeitoRecord] = field(default_factory=dict)      # key: hansyoku_num


def parse_input(input_dir: str) -> ParsedData:
    """生データディレクトリを読み、レコード種別ごとに dataclass 列へ変換する。

    TODO: 実装。JV-Link ダンプ形式に応じて、
      1. ファイル/ストリームを走査
      2. 先頭のレコード種別ID (UM/HN/SK/BT) で分岐
      3. JVData_Struct.py の SetDataB のオフセットに従って各フィールドを切り出す
      4. ParsedData に格納
    現状はスキャフォールドのため空を返す。
    """
    raise NotImplementedError("生データのパースは実データ形式確認後に実装する")
