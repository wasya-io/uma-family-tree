"""JV-Data レコードのパース。

対象レコード (`.refarence/.../JV-Data構造体/Python版/JVData_Struct.py` の構造体に対応):

- UM (JV_UM_UMA)       競走馬マスタ   … KettoNum, 馬名/カナ/英字, 性別, 毛色, 生年月日, 3代血統
- HN (JV_HN_HANSYOKU)  繁殖馬マスタ   … HansyokuNum, KettoNum, 親ポインタ(F/M), 馬名, 性別, 毛色, 生年
- SK (JV_SK_SANKU)     産駒マスタ     … KettoNum, 3代血統の繁殖番号
- BT (JV_BT_KEITO)     系統情報       … HansyokuNum, KeitoId, KeitoName

各レコードは shift_jis (cp932) の固定長バイト列で、CR/LF 区切り。先頭2バイトがレコード種別ID。

【重要】繁殖登録番号は 8 桁フォーマット
  JVData_Struct.py (2026年版) は繁殖登録番号を 10 桁前提でオフセットを組んでいるが、
  今回取得した実データ (HN=243バイト固定) は **8桁** フォーマットだった。そのため
  HN/BT のオフセットは構造体仕様から 2 バイトずつ手前にずれる。以下のオフセットは
  実データに対する参照整合性検証 (HN.FNum→HN.HansyokuNum が 100% 一致) で確定済み。

  確定オフセット (1-based):
    HN: HansyokuNum[12,8] KettoNum[28,10] Bamei[39,36] Kana[75,40] Eng[115,80]
        BirthYear[195,4] SexCD[199,1] KeiroCD[201,2] FNum[228,8] MNum[236,8]
    BT: HansyokuNum[12,8] KeitoId[22,?] KeitoName[50,36]
    UM: KettoNum[12,10] BirthDate[39,8] Bamei[47,36] Kana[83,36] Eng[119,60]
        SexCD[201,1] KeiroCD[203,2] Ketto3: base205, 要素stride44 (HansyokuNum8+名36)

downloader が出力する input/{UM,HN,SK,BT}.dat を読み、種別ごとの dataclass 列へ変換する。
UM.dat は数百MB あるため、全体を一度に読まず1レコードずつ処理する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ENCODING = "cp932"


def _s(b: bytes, start: int, length: int) -> str:
    """JVData_Struct.py の MidB2S と同じ: 1-based start でバイト切出し → cp932 デコード → 前後空白除去。

    JV-Data の文字列は全角/半角スペースで右詰めパディングされるため strip する。
    """
    raw = b[start - 1 : start - 1 + length]
    return raw.decode(ENCODING, errors="ignore").strip("\u3000 \x00")


def _int(v: str) -> int:
    """数字文字列 (前後空白・ゼロ埋め) を int に。空/非数字は 0。"""
    v = v.strip()
    return int(v) if v.isdigit() else 0


def _year(b: bytes, start: int, length: int) -> int | None:
    """4桁の年 (または YMD 先頭4桁) を int に。妥当でなければ None。"""
    v = _s(b, start, length)
    if len(v) >= 4 and v[:4].isdigit():
        y = int(v[:4])
        if 1700 <= y <= 2100:
            return y
    return None


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
    # 父・母の繁殖登録番号 (Ketto3Info の先頭2頭 = 父[0], 母[1])。
    father_hansyoku_num: str = ""
    mother_hansyoku_num: str = ""
    # 実績 (代表子孫の優先表示に使う)。
    earnings: int = 0                  # 平地本賞金累計 (単位: 100円。JV-Data の生値)
    wins: int = 0                      # 総合着回数の1着回数 (中央+地方+海外)
    starts: int = 0                    # 総合着回数の合計 (出走数の近似)

    @classmethod
    def parse(cls, b: bytes) -> "UmaRecord":
        # Ketto3Info: 8桁フォーマットでは base=205、要素 stride=44 (HansyokuNum8 + Bamei36)。
        # i=0 が父、i=1 が母。(実データで父名=213, 母名=257 を確認)
        def ketto3_hansyoku(i: int) -> str:
            return _s(b, 205 + 44 * i, 8)

        # 実績フィールドのオフセット (8桁 UM.dat = 1575バイト固定長で実証済み):
        #   平地本賞金累計 [1021,9] / 総合着回数 [1075, 3×6=18] / 登録レース数 [1573,3]
        #   総合着回数 = [1着,2着,3着,4着,5着,着外] の各3桁。
        #   検証: キタサンブラック=012,002,004,000,000,002 (20戦12勝), 本賞金 018132000。
        #          ディープインパクト=012,001,000,000,000,001 (14戦12勝), 本賞金 013240000。
        chaku = [_s(b, 1075 + 3 * i, 3) for i in range(6)]
        wins = _int(chaku[0])
        starts = sum(_int(c) for c in chaku)

        return cls(
            ketto_num=_s(b, 12, 10),
            birth_year=_year(b, 39, 8),   # BirthDate YMD の先頭4桁
            name=_s(b, 47, 36),
            kana=_s(b, 83, 36),
            eng=_s(b, 119, 60),
            sex_cd=_s(b, 201, 1),
            keiro_cd=_s(b, 203, 2),
            father_hansyoku_num=ketto3_hansyoku(0),
            mother_hansyoku_num=ketto3_hansyoku(1),
            earnings=_int(_s(b, 1021, 9)),
            wins=wins,
            starts=starts,
        )


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

    @classmethod
    def parse(cls, b: bytes) -> "HansyokuRecord":
        # 8桁繁殖登録番号フォーマット。オフセットは実データで参照整合性検証済み。
        return cls(
            hansyoku_num=_s(b, 12, 8),
            ketto_num=_s(b, 28, 10),
            name=_s(b, 39, 36),
            kana=_s(b, 75, 40),
            eng=_s(b, 115, 80),
            birth_year=_year(b, 195, 4),
            sex_cd=_s(b, 199, 1),
            keiro_cd=_s(b, 201, 2),
            father_hansyoku_num=_s(b, 228, 8),
            mother_hansyoku_num=_s(b, 236, 8),
        )


@dataclass
class KeitoRecord:
    """系統情報 (BT)。HansyokuNum → 系統。"""

    hansyoku_num: str
    keito_id: str = ""                 # 系統ID (色分けキー)
    keito_name: str = ""               # 系統名

    @classmethod
    def parse(cls, b: bytes) -> "KeitoRecord":
        # 8桁フォーマット。実データで KeitoId=22, KeitoName=50 と確認。
        return cls(
            hansyoku_num=_s(b, 12, 8),
            keito_id=_s(b, 22, 28),
            keito_name=_s(b, 50, 36),
        )


@dataclass
class ParsedData:
    """パース結果の集約。graph 構築の入力になる。"""

    uma: dict[str, UmaRecord] = field(default_factory=dict)            # key: ketto_num
    hansyoku: dict[str, HansyokuRecord] = field(default_factory=dict)  # key: hansyoku_num
    keito: dict[str, KeitoRecord] = field(default_factory=dict)        # key: hansyoku_num


def _iter_records(path: Path):
    """CR/LF 区切りの固定長レコードを1件ずつ bytes で返す。大容量ファイル向けに逐次処理。"""
    if not path.exists():
        return
    with open(path, "rb") as f:
        for line in f:
            rec = line.rstrip(b"\r\n")
            if len(rec) >= 2:
                yield rec


def parse_input(input_dir: str) -> ParsedData:
    """生データディレクトリ (UM/HN/SK/BT.dat) を読み、ParsedData を構築する。

    SK (産駒マスタ) は現状 UM/HN で血統を辿れるため未使用だが、将来の補完用に予約。
    """
    d = Path(input_dir)
    data = ParsedData()

    for rec in _iter_records(d / "UM.dat"):
        u = UmaRecord.parse(rec)
        if u.ketto_num:
            data.uma[u.ketto_num] = u

    for rec in _iter_records(d / "HN.dat"):
        h = HansyokuRecord.parse(rec)
        if h.hansyoku_num:
            data.hansyoku[h.hansyoku_num] = h

    for rec in _iter_records(d / "BT.dat"):
        k = KeitoRecord.parse(rec)
        if k.hansyoku_num:
            data.keito[k.hansyoku_num] = k

    return data
