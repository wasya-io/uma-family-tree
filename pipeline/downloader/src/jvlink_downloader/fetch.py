"""JV-Link 一括ダウンロード (ヘッドレス)。

SDK の Python サンプル (Form1.py / Form2.py) の JVInit → JVOpen → JVStatus →
JVGets → JVClose の流れを、GUI なしの CLI に移植したもの。

取得したレコードは、先頭2バイトのレコード種別ID (UM/HN/SK/BT ...) ごとに
出力ディレクトリ内のファイル (例: UM.dat) へ追記する。pipeline はこれを入力に取る。
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path

from . import config


def _load_jvlink():
    """JVLink COM オブジェクトを生成する。Windows 以外では明確なエラーにする。

    JVGets は Byte Array の [in,out] や複数の [out] 引数を持つ複雑なシグネチャで、
    遅延バインディング (Dispatch) だと型情報が無いため win32com のマーシャリングが
    不安定になり、"SystemError: returned a result with an exception set" が発生する。
    そこで **早期バインディング** (gencache.EnsureDispatch = makepy でタイプライブラリから
    型情報を生成) を優先して使う。取得できない環境では Dispatch にフォールバックする。
    """
    if sys.platform != "win32":
        raise RuntimeError(
            "JV-Link は Windows 専用です。この環境 (%s) では実行できません。" % sys.platform
        )
    import win32com.client  # type: ignore  # Windows のみ

    try:
        # 早期バインディング (型情報つき)。JVGets の out 引数マーシャリングが安定する。
        return win32com.client.gencache.EnsureDispatch("JVDTLab.JVLink")
    except Exception as e:  # noqa: BLE001
        # タイプライブラリ生成に失敗した場合は遅延バインディングにフォールバック。
        print(f"警告: 早期バインディングに失敗 ({e})。Dispatch にフォールバックします。")
        return win32com.client.Dispatch("JVDTLab.JVLink")


def _jvopen(jvlink, dataspec: str, fromtime: str, option: int):
    """JVOpen を呼び、(code, read_count, download_count, lastfiletime) を返す。

    サンプルに倣い、戻り値がタプルの場合と単一コードの場合の両方に対応。
    """
    ret = jvlink.JVOpen(dataspec, fromtime, option, 0, 0, "")
    if isinstance(ret, (list, tuple)):
        code = int(ret[0])
        read_count = int(ret[1] or 0)
        download_count = int(ret[2] or 0)
        lastfiletime = str(ret[3] or "")
        return code, read_count, download_count, lastfiletime
    return int(ret), 0, 0, ""


def _wait_download(jvlink, download_count: int) -> None:
    """JVStatus をポーリングしてダウンロード完了を待つ。"""
    if download_count == 0:
        return
    while True:
        status = jvlink.JVStatus()
        if status < 0:
            raise RuntimeError(f"JVStatus エラー: {status}")
        print(f"  ダウンロード中... ({status}/{download_count})", end="\r", flush=True)
        if status >= download_count:
            break
        time.sleep(0.3)
    print()


class _RecordWriter:
    """レコード種別 (先頭2バイト) ごとに出力ファイルへ振り分けて書き出す。

    append=False (既定) は上書き (wb)。データ種別を分割して複数回実行する場合、
    2回目以降は別のレコード種別を書くので上書きでも衝突しないが、同じレコード種別を
    追記したいときは append=True (ab) を使う。
    """

    def __init__(self, out_dir: Path, append: bool = False):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._mode = "ab" if append else "wb"
        self._handles: dict[str, object] = {}
        self.counts: dict[str, int] = {}

    def write(self, raw: bytes) -> None:
        if len(raw) < 2:
            return
        rectype = raw[:2].decode(config.ENCODING, errors="replace")
        # 血統可視化に不要なレコード種別 (RA/SE/オッズ等) は捨てる。
        if config.KEEP_RECORD_TYPES and rectype not in config.KEEP_RECORD_TYPES:
            return
        fh = self._handles.get(rectype)
        if fh is None:
            fh = open(self.out_dir / f"{rectype}.dat", self._mode)
            self._handles[rectype] = fh
            self.counts[rectype] = 0
        fh.write(raw)  # type: ignore[attr-defined]
        self.counts[rectype] += 1

    def close(self) -> None:
        for fh in self._handles.values():
            fh.close()  # type: ignore[attr-defined]


def _extract_record(memview, buff: bytearray, ret: int) -> bytes | None:
    """JVGets の結果からレコード ret バイトを取り出す。

    win32com の JVGets は戻り値の形が環境・レコードで揺れる:
      - memview (memoryview / bytes 相当) にデータが入る場合
      - memview が None で、入力バッファ buff 側にデータが格納される場合
    どちらでも先頭 ret バイトを取り出せるようにする。取り出せなければ None。
    """
    # 1) memview が使える場合はそれを優先。
    if memview is not None:
        try:
            return bytes(memview[:ret])
        except TypeError:
            # memview がスライス不可の型 (稀) の場合は bytes 化を試す。
            try:
                return bytes(memview)[:ret]
            except Exception:  # noqa: BLE001
                pass
    # 2) フォールバック: 入力バッファ buff の先頭 ret バイト。
    if buff is not None and len(buff) >= ret:
        return bytes(buff[:ret])
    return None


def _read_all(jvlink, writer: _RecordWriter, read_count: int) -> None:
    """JVGets ループ。ret>0=データ, -1=ファイル切替, 0=EOF, その他=エラー。

    メモリ対策:
      - 入力バッファはループ外で1回だけ確保して使い回す (毎回 110KB を新規確保しない)。
      - JVGets が返す memoryview は tobytes() でコピーした直後に参照を解放する
        (COM 側 SAFEARRAY を溜め込まないため)。
      - フル・セットアップは数百万レコードに及ぶため、これを怠るとメモリが枯渇する。
    """
    readed = 0
    records = 0
    buff = bytearray(config.BUFFER_SIZE)
    while True:
        buffname = bytearray()
        ret, memview, _fname = jvlink.JVGets(buff, config.BUFFER_SIZE, buffname)
        ret = int(ret)
        if ret > 0:
            # レコードデータを取り出す。JVGets は環境により、戻り値の memview に
            # データを返す場合と、入力バッファ buff 側に格納する場合がある。
            # memview が None のときは buff から読む (両対応で堅牢化)。
            record = _extract_record(memview, buff, ret)
            memview = None
            if record is not None:
                writer.write(record)
            records += 1
            # win32com が JVGets 呼び出しごとに溜め込む COM オブジェクトを定期的に回収する。
            # (これをしないと数百万レコードでメモリが枯渇し MemoryError になる)
            if records % config.GC_INTERVAL == 0:
                gc.collect()
                print(f"  読込み {records} 件 処理中...", end="\r", flush=True)
        elif ret == -1:
            readed += 1
            if read_count:
                print(f"  読込み中... ({readed}/{read_count})", end="\r", flush=True)
        elif ret == 0:
            print(f"\n  読込み完了 (レコード {records} 件)")
            break
        else:
            raise RuntimeError(f"JVGets エラー: {ret}")


def fetch(
    out_dir: Path, dataspec: str, fromtime: str, option: int, append: bool = False
) -> dict[str, int]:
    """一括ダウンロードを実行し、レコード種別ごとの件数を返す。"""
    jvlink = _load_jvlink()

    ret = jvlink.JVInit(config.SOFTWARE_ID)
    if ret != 0:
        raise RuntimeError(f"JVInit エラー: {ret}")
    print(f"JVInit 正常 (SoftwareID={config.SOFTWARE_ID})")

    try:
        print(f"JVOpen: dataspec={dataspec} fromtime={fromtime} option={option}")
        code, read_count, download_count, lastfiletime = _jvopen(
            jvlink, dataspec, fromtime, option
        )
        # 切り分け用に JVOpen の戻り値を全て出す。
        print(
            f"JVOpen 戻り値: code={code} readcount={read_count} "
            f"downloadcount={download_count} lastfiletimestamp='{lastfiletime}'"
        )
        if code == -1:
            print(
                "該当データなし (-1): 指定条件に合致する新しいデータがサーバに無い。\n"
                "  切り分けのヒント:\n"
                "   - readcount が 0 以外なら、ローカルに該当ファイルがある可能性。\n"
                "   - option=1 で近い日付を fromtime に指定して通常データで試す:\n"
                "       uv run jvlink-fetch --option 1 --fromtime 20240101000000\n"
                "   - JV-Link 設定 (利用キー) が未設定だと該当なしになることがある:\n"
                "       uv run jvlink-setup"
            )
            return {}
        if code != 0:
            raise RuntimeError(f"JVOpen エラー: {code}")
        print(f"JVOpen 正常 Read={read_count} Download={download_count}")

        _wait_download(jvlink, download_count)

        writer = _RecordWriter(out_dir, append=append)
        try:
            _read_all(jvlink, writer, read_count)
        finally:
            writer.close()

        if lastfiletime:
            # 差分取得の起点として保存しておく。
            (out_dir / "lastfiletime.txt").write_text(lastfiletime, encoding="ascii")
        return writer.counts
    finally:
        try:
            jvlink.JVClose()
            print("JVClose 正常")
        except Exception as e:  # noqa: BLE001
            print(f"JVClose 例外(無視): {e}")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jvlink-fetch",
        description="JV-Link から血統可視化用の蓄積系データを一括ダウンロードする (Windows 専用)",
    )
    p.add_argument("--out", type=Path, default=Path("..") / "input", help="生データ出力先")
    p.add_argument(
        "--dataspec", default=config.DATASPEC,
        help="取得データ種別 (既定: config.DATASPEC)。メモリ対策で 'DIFF' と 'BLOD' に分けて "
             "別プロセスで実行するのを推奨 (fetch.bat 参照)。",
    )
    p.add_argument("--fromtime", default=config.FROMTIME_ALL, help="取得開始日時 YYYYMMDDhhmmss")
    p.add_argument("--option", type=int, default=config.DEFAULT_OPTION, help="JVOpen option (1/2/3/4)")
    p.add_argument(
        "--append", action="store_true",
        help="既存の .dat に追記する (既定は上書き)。分割実行で同じレコード種別を継ぎ足す場合に使う。",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    counts = fetch(args.out, args.dataspec, args.fromtime, args.option, append=args.append)
    if counts:
        print("取得件数:")
        for rectype, n in sorted(counts.items()):
            print(f"  {rectype}: {n}")
    print(f"出力先: {args.out}")


if __name__ == "__main__":
    main()
