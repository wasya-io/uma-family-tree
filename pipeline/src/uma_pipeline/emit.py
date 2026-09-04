"""配信用 JSON の書き出し。

docs/design.md §3 のデータ形式に従って以下を生成する:

- horses/{KettoNum}.json   馬ノードファイル (祖先 M 代 + 子孫 L 代の事前展開サブグラフ)
- search-index.json        検索辞書 (カナ/英字 → KettoNum)
- keito-master.json        系統マスタ
- full/{KettoNum}.json     全部盛り専用ファイル (限定始祖の全子孫)
"""

from __future__ import annotations

import json
from pathlib import Path

from .graph import Edge, Node, PedigreeGraph

# 事前展開の最大範囲 (案B折衷のたたき台)。UI の深さ最大値に一致させる。
DEFAULT_ANCESTOR_DEPTH = 5
DEFAULT_DESCENDANT_DEPTH = 3


def _node_to_dict(node: Node, generation: int) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "kana": node.kana,
        "eng": node.eng,
        "sex": node.sex,
        "color": node.color,
        "birthYear": node.birth_year,
        "keitoId": node.keito_id or "other",
        "generation": generation,
    }


def _edge_to_dict(edge: Edge) -> dict:
    return {"source": edge.source, "target": edge.target, "parent": edge.parent}


def write_horse_files(
    graph: PedigreeGraph,
    out_dir: Path,
    ancestor_depth: int = DEFAULT_ANCESTOR_DEPTH,
    descendant_depth: int = DEFAULT_DESCENDANT_DEPTH,
) -> int:
    """全馬について horses/{id}.json を書き出す。戻り値は生成ファイル数。

    TODO: 各ノードを中心に graph.ancestors / graph.descendants でサブグラフを切り出し、
          center/nodes/edges を組み立てて書き出す。generation は中心=0, 祖先=+n, 子孫=-n。
    """
    raise NotImplementedError


def write_search_index(graph: PedigreeGraph, out_path: Path) -> None:
    """search-index.json を書き出す (id/kana/eng の配列)。"""
    index = [
        {"id": n.id, "kana": n.kana, "eng": n.eng}
        for n in graph.nodes.values()
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def write_keito_master(master: dict[str, dict[str, str]], out_path: Path) -> None:
    """keito-master.json を書き出す。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")


def write_full_files(
    graph: PedigreeGraph,
    founder_ids: list[str],
    out_dir: Path,
) -> int:
    """全部盛り専用ファイル full/{id}.json を、限定始祖リストについて書き出す。

    TODO: founder_ids の各馬について子孫を無制限に展開し、nodes/edges を書き出す。
    """
    raise NotImplementedError
