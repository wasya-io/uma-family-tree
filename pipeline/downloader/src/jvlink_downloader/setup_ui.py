"""JV-Link の設定 UI を開く補助 (JVSetUIProperties)。

初回のみ、JRA-VAN 利用キー等を設定するために実行する。
    python -m jvlink_downloader.setup_ui
"""

from __future__ import annotations

from .fetch import _load_jvlink
from . import config


def main() -> None:
    jvlink = _load_jvlink()
    ret = jvlink.JVInit(config.SOFTWARE_ID)
    if ret != 0:
        print(f"JVInit エラー: {ret}")
        return
    print("JV-Link 設定 UI を開きます...")
    jvlink.JVSetUIProperties()
    jvlink.JVClose()


if __name__ == "__main__":
    main()
