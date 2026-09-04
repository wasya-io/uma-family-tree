"""JV-Link の利用キー (サービスキー) を設定する補助 (JVSetServiceKey)。

利用キーは 17 桁の英数字。設定するとレジストリに保存され、以降の
JVInit / JVOpen で使われる (仕様書 JVSetServiceKey 参照)。

使い方:
    uv run jvlink-setkey <17桁の利用キー>

戻り値 0=成功 / -100=不正な値 (または既に設定済みで変更不可)。
"""

from __future__ import annotations

import argparse

from .fetch import _load_jvlink
from . import config


def set_service_key(servicekey: str) -> int:
    key = servicekey.strip()
    if len(key) != 17:
        print(f"警告: 利用キーは通常17桁です (入力={len(key)}桁)。そのまま設定を試みます。")
    jvlink = _load_jvlink()
    ret = jvlink.JVInit(config.SOFTWARE_ID)
    if ret != 0:
        print(f"JVInit エラー: {ret}")
        return ret
    ret = int(jvlink.JVSetServiceKey(key))
    if ret == 0:
        print("利用キーを設定しました (JVSetServiceKey=0)。")
    elif ret == -100:
        print(
            "JVSetServiceKey=-100: 値が不正、または既に設定済みで変更不可です。\n"
            "  既存キーを変更したい場合は JV-Link 設定 UI (uv run jvlink-setup) から行ってください。"
        )
    else:
        print(f"JVSetServiceKey 戻り値: {ret}")
    try:
        jvlink.JVClose()
    except Exception:  # noqa: BLE001
        pass
    return ret


def main() -> None:
    p = argparse.ArgumentParser(
        prog="jvlink-setkey",
        description="JV-Link の利用キー (サービスキー, 17桁) を設定する",
    )
    p.add_argument("servicekey", help="JRA-VAN の利用キー (17桁の英数字)")
    args = p.parse_args()
    set_service_key(args.servicekey)


if __name__ == "__main__":
    main()
