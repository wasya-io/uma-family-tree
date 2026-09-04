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
        "kettoNum": node.ketto_num,
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


def _generation_map(
    graph: PedigreeGraph, center: str, ancestor_depth: int, descendant_depth: int
) -> dict[str, int]:
    """中心からの世代 (祖先=+n, 子孫=-n, 中心=0) を割り当てる。

    DAG なので同一ノードが複数経路で到達し得る。祖先/子孫それぞれ BFS し、
    絶対値が最小の世代を採用する (最短距離)。
    """
    gen: dict[str, int] = {center: 0}
    # 祖先方向 (親をたどる)
    _bfs_gen(graph.parents_of, center, ancestor_depth, +1, gen, use_source=True)
    # 子孫方向 (子をたどる)
    _bfs_gen(graph.children_of, center, descendant_depth, -1, gen, use_source=False)
    return gen


def _bfs_gen(adj, start, depth, sign, gen, use_source):
    from collections import deque

    q = deque([(start, 0)])
    seen = {start}
    while q:
        cur, d = q.popleft()
        if d >= depth:
            continue
        for e in adj.get(cur, ()):
            nxt = e.source if use_source else e.target
            if nxt not in seen:
                seen.add(nxt)
                g = sign * (d + 1)
                # 既存の世代があれば絶対値が小さい方を優先
                if nxt not in gen or abs(g) < abs(gen[nxt]):
                    gen[nxt] = g
                q.append((nxt, d + 1))


def _subgraph(graph: PedigreeGraph, center: str, gen: dict[str, int]) -> dict:
    """世代マップに含まれるノード集合で誘導部分グラフを作り、JSON dict を返す。"""
    ids = set(gen)
    nodes = [_node_to_dict(graph.nodes[i], gen[i]) for i in ids if i in graph.nodes]
    edges = []
    for i in ids:
        for e in graph.parents_of.get(i, ()):
            if e.source in ids and e.target in ids:
                edges.append(_edge_to_dict(e))
    return {"center": center, "nodes": nodes, "edges": edges}


def write_horse_files(
    graph: PedigreeGraph,
    out_dir: Path,
    ancestor_depth: int = DEFAULT_ANCESTOR_DEPTH,
    descendant_depth: int = DEFAULT_DESCENDANT_DEPTH,
    only: str | None = None,
    limit: int | None = None,
) -> int:
    """馬ファイル horses/{id}.json を書き出す。戻り値は生成ファイル数。

    各ノードを中心に、祖先 ancestor_depth 代 + 子孫 descendant_depth 代の
    誘導部分グラフを切り出して書き出す。generation は中心=0, 祖先=+n, 子孫=-n。

    only: 指定した KettoNum または ノードid の馬だけ生成 (検証用)。
    limit: 生成数の上限 (全件は数十万になるための安全弁)。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    targets: list[str]
    if only:
        nid = only if only in graph.nodes else _resolve_by_ketto(graph, only)
        targets = [nid] if nid else []
    else:
        targets = list(graph.nodes)
        if limit is not None:
            targets = targets[:limit]

    count = 0
    for nid in targets:
        gen = _generation_map(graph, nid, ancestor_depth, descendant_depth)
        sub = _subgraph(graph, nid, gen)
        (out_dir / f"{nid}.json").write_text(
            json.dumps(sub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        count += 1
    return count


def _resolve_by_ketto(graph: PedigreeGraph, ketto_num: str) -> str | None:
    """KettoNum からノード id を引く。"""
    for n in graph.nodes.values():
        if n.ketto_num == ketto_num:
            return n.id
    return None


def write_search_index(graph: PedigreeGraph, out_path: Path) -> None:
    """search-index.json を書き出す (id/name/kana/eng の配列)。

    名前が空のノード (古い始祖でデータ欠損等) は検索対象から除外する。
    """
    index = [
        {"id": n.id, "name": n.name, "kana": n.kana, "eng": n.eng}
        for n in graph.nodes.values()
        if n.name or n.kana or n.eng
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

    founder_ids の各馬について子孫を (実質) 無制限に展開する。祖先は含めない
    (始祖なので祖先方向は不要)。generation は中心=0, 子孫=-n。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    BIG = 10_000
    for nid in founder_ids:
        if nid not in graph.nodes:
            continue
        gen = _generation_map(graph, nid, ancestor_depth=0, descendant_depth=BIG)
        sub = _subgraph(graph, nid, gen)
        (out_dir / f"{nid}.json").write_text(
            json.dumps(sub, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        count += 1
    return count
