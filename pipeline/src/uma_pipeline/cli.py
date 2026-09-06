"""パイプラインのエントリポイント。

    uma-pipeline --input ./input --output ./output

生データを読み → 血統 DAG を構築 → D1 投入用の .sql を出力する。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import emit, keito
from .graph import build_graph
from .records import parse_input


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="uma-pipeline",
        description="JV-Link 生データを血統 DAG の D1 投入用 SQL に加工する",
    )
    p.add_argument("--input", required=True, type=Path, help="生データディレクトリ")
    p.add_argument("--output", required=True, type=Path, help="出力ディレクトリ")
    p.add_argument(
        "--sql-name", default="pedigree.sql",
        help="出力する SQL ファイル名 (output 直下)",
    )
    return p


def run(args: argparse.Namespace) -> None:
    print(f"[1/4] 生データをパース: {args.input}")
    data = parse_input(str(args.input))
    print(f"  UM={len(data.uma)} HN={len(data.hansyoku)} BT={len(data.keito)}")

    print("[2/4] 血統 DAG を構築")
    graph = build_graph(data)
    n_edges = sum(len(v) for v in graph.parents_of.values())
    print(f"  nodes={len(graph.nodes)} edges={n_edges}")

    print("[3/4] 系統マスタを生成")
    keito_names = {r.keito_id: r.keito_name for r in data.keito.values()}
    master = keito.build_keito_master(graph, keito_names)

    # データ基準時点 (ダウンロード時に保存した lastfiletime.txt)。
    meta: dict[str, str] = {}
    lastfiletime_path = args.input / "lastfiletime.txt"
    if lastfiletime_path.exists():
        ts = lastfiletime_path.read_text(encoding="ascii").strip()
        if ts:
            meta["data_timestamp"] = ts  # YYYYMMDDhhmmss
            print(f"  データ基準時点: {ts}")

    print("[4/4] D1 投入用 SQL を書き出し")
    sql_path = args.output / args.sql_name
    counts = emit.write_sql(graph, master, sql_path, meta=meta)
    print(
        f"  horses={counts['horses']} edges={counts['edges']} "
        f"keito={counts['keito']} meta={counts['meta']}"
    )
    print(f"完了: {sql_path}")


def main() -> None:
    args = build_arg_parser().parse_args()
    run(args)


if __name__ == "__main__":
    main()
