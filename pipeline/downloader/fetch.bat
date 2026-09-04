@echo off
rem ========================================================================
rem  JV-Link 一括ダウンロード (1 クリック実行)
rem  このバッチを置いたフォルダ (pipeline\downloader) で uv 経由の
rem  取得スクリプトを実行し、生データを pipeline\input へ書き出す。
rem ========================================================================

rem バッチ自身のフォルダへ移動 (どこから起動しても動くように)
cd /d "%~dp0"

rem uv 環境で取得スクリプトを実行。
rem 初回はセットアップデータ全件 (option=3, fromtime=全期間)。
uv run jvlink-fetch --out "..\input" --fromtime 00000000000000 --option 3

echo.
echo 完了しました。何かキーを押すと閉じます。
pause >nul
