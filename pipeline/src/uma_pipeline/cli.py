"""パイプラインのエントリポイント。

    uma-pipeline --input ./input --output ./output

生データを読み → 血統 DAG を構築 → 配信用 JSON 群を出力する。
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
        description="JV-Link 生データを血統 DAG の配信用 JSON に加工する",
    )
    p.add_argument("--input", required=True, type=Path, help="生データディレクトリ")
    p.add_argument("--output", required=True, type=Path, help="JSON 出力ディレクトリ")
    p.add_argument(
        "--ancestor-depth", type=int, default=emit.DEFAULT_ANCESTOR_DEPTH,
        help="馬ノードファイルに事前展開する祖先の代数",
    )
    p.add_argument(
        "--descendant-depth", type=int, default=emit.DEFAULT_DESCENDANT_DEPTH,
        help="馬ノードファイルに事前展開する子孫の代数",
    )
    p.add_argument(
        "--founders", type=Path, default=None,
        help="全部盛り対象の始祖 KettoNum を1行1件で列挙したファイル (任意)",
    )
    return p


def run(args: argparse.Namespace) -> None:
    print(f"[1/4] 生データをパース: {args.input}")
    data = parse_input(str(args.input))

    print("[2/4] 血統 DAG を構築")
    graph = build_graph(data)

    print("[3/4] 系統マスタを生成")
    keito_names = {r.keito_id: r.keito_name for r in data.keito.values()}
    master = keito.build_keito_master(graph, keito_names)
    emit.write_keito_master(master, args.output / "keito-master.json")

    print("[4/4] 馬ノード・検索インデックスを書き出し")
    emit.write_search_index(graph, args.output / "search-index.json")
    n = emit.write_horse_files(
        graph, args.output / "horses",
        ancestor_depth=args.ancestor_depth,
        descendant_depth=args.descendant_depth,
    )
    print(f"  馬ノードファイル {n} 件")

    if args.founders and args.founders.exists():
        founder_ids = [
            line.strip()
            for line in args.founders.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        m = emit.write_full_files(graph, founder_ids, args.output / "full")
        print(f"  全部盛りファイル {m} 件")

    print(f"完了: {args.output}")


def main() -> None:
    args = build_arg_parser().parse_args()
    run(args)


if __name__ == "__main__":
    main()
