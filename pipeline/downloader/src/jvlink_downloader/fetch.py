"""JV-Link 一括ダウンロード (ヘッドレス)。

SDK の Python サンプル (Form1.py / Form2.py) の JVInit → JVOpen → JVStatus →
JVGets → JVClose の流れを、GUI なしの CLI に移植したもの。

取得したレコードは、先頭2バイトのレコード種別ID (UM/HN/SK/BT ...) ごとに
出力ディレクトリ内のファイル (例: UM.dat) へ追記する。pipeline はこれを入力に取る。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import config


def _load_jvlink():
    """JVLink COM オブジェクトを生成する。Windows 以外では明確なエラーにする。"""
    if sys.platform != "win32":
        raise RuntimeError(
            "JV-Link は Windows 専用です。この環境 (%s) では実行できません。" % sys.platform
        )
    import win32com.client  # type: ignore  # Windows のみ

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
    """レコード種別 (先頭2バイト) ごとに出力ファイルへ振り分けて書き出す。"""

    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, object] = {}
        self.counts: dict[str, int] = {}

    def write(self, raw: bytes) -> None:
        if len(raw) < 2:
            return
        rectype = raw[:2].decode(config.ENCODING, errors="replace")
        # 血統可視化に不要なレコード種別 (DIFF に含まれる RA/SE/オッズ等) は捨てる。
        if config.KEEP_RECORD_TYPES and rectype not in config.KEEP_RECORD_TYPES:
            return
        fh = self._handles.get(rectype)
        if fh is None:
            fh = open(self.out_dir / f"{rectype}.dat", "wb")
            self._handles[rectype] = fh
            self.counts[rectype] = 0
        fh.write(raw)  # type: ignore[attr-defined]
        self.counts[rectype] += 1

    def close(self) -> None:
        for fh in self._handles.values():
            fh.close()  # type: ignore[attr-defined]


def _read_all(jvlink, writer: _RecordWriter, read_count: int) -> None:
    """JVGets ループ。ret>0=データ, -1=ファイル切替, 0=EOF, その他=エラー。"""
    readed = 0
    while True:
        buff = bytearray(config.BUFFER_SIZE)
        buffname = bytearray()
        ret, memview, _fname = jvlink.JVGets(buff, config.BUFFER_SIZE, buffname)
        ret = int(ret)
        if ret > 0:
            writer.write(memview.tobytes())
        elif ret == -1:
            readed += 1
            if read_count:
                print(f"  読込み中... ({readed}/{read_count})", end="\r", flush=True)
        elif ret == 0:
            print("\n  読込み完了")
            break
        else:
            raise RuntimeError(f"JVGets エラー: {ret}")


def fetch(out_dir: Path, dataspec: str, fromtime: str, option: int) -> dict[str, int]:
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
        if code == -1:
            print("該当データなし")
            return {}
        if code != 0:
            raise RuntimeError(f"JVOpen エラー: {code}")
        print(f"JVOpen 正常 Read={read_count} Download={download_count}")

        _wait_download(jvlink, download_count)

        writer = _RecordWriter(out_dir)
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
    p.add_argument("--dataspec", default=config.DATASPEC, help="取得データ種別 (既定: config.DATASPEC)")
    p.add_argument("--fromtime", default=config.FROMTIME_ALL, help="取得開始日時 YYYYMMDDhhmmss")
    p.add_argument("--option", type=int, default=config.DEFAULT_OPTION, help="JVOpen option (1/2/3)")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    counts = fetch(args.out, args.dataspec, args.fromtime, args.option)
    if counts:
        print("取得件数:")
        for rectype, n in sorted(counts.items()):
            print(f"  {rectype}: {n}")
    print(f"出力先: {args.out}")


if __name__ == "__main__":
    main()
