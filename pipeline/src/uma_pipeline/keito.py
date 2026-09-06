"""系統マスタの生成 (主要系統への丸め込み)。

BT (系統情報) は JV-VAN が分類済み (HansyokuNum -> KeitoId/KeitoName)。
KeitoId は「2桁ごとに系譜を表現する」階層 ID (例: 01080201010201 = サンデーサイレンス系)。
各ノードの keito_id は、父系をさかのぼって見つかる最も具体的な系統 ID になっている
(graph._propagate_keito)。ただし種類が多く (実データで ~91)、そのまま色分けすると
細かすぎる & マスタと完全一致しないノードが多発する。

そこで:
  1. BT の全系統 (id -> name) を候補アンカーとする。
  2. 各ノードの keito_id を、「その keito_id の接頭辞になっている BT 系統 ID のうち最長のもの」
     に解決する (= その馬が属する最も具体的な "名前付き系統")。
  3. 解決先の系統ごとにノード数を数え、上位 N を「主要系統」として固有色を与える。
  4. 主要系統に属さないノードは、さらに上位の主要系統へ (より短い接頭辞で) 丸める。
     どれにも当たらなければ "other"。

これにより、ノードの keito_id は最終的に「主要系統 ID」または "other" に正規化され、
viewer 側は keito_master との完全一致で色を引ける。
"""

from __future__ import annotations

from collections import Counter

from .graph import PedigreeGraph

# 主要系統に割り当てる固有色 (識別しやすい配色)。
PALETTE: list[str] = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
    "#9a6324", "#808000", "#000075", "#e6beff", "#aaffc3",
    "#ffd8b1", "#a9a9a9", "#fffac8", "#800000", "#000000",
]
OTHER_COLOR = "#999999"
OTHER_LABEL = "その他"
OTHER_ID = "other"


def _longest_prefix_match(keito_id: str, anchors: list[str]) -> str | None:
    """keito_id の接頭辞になっている anchor のうち最長のものを返す。無ければ None。

    anchors は長い順に並んでいる前提。
    """
    for a in anchors:
        if keito_id.startswith(a):
            return a
    return None


def build_keito_master(
    graph: PedigreeGraph,
    keito_names: dict[str, str],
    top_n: int = len(PALETTE),
) -> dict[str, dict[str, str]]:
    """主要系統マスタ (keitoId -> {name, color}) を生成し、
    同時に graph 内の各ノードの keito_id を主要系統 ID に正規化する (副作用)。

    Args:
        graph: 構築済み血統 DAG (各ノードの keito_id を参照・書き換える)。
        keito_names: keitoId -> 系統名 (BT レコードから収集)。
        top_n: 固有色を割り当てる主要系統数。
    """
    # BT 系統 ID を長い順に (最長一致のため)。
    anchors = sorted((k for k in keito_names if k), key=len, reverse=True)

    # 1st pass: 各ノードを最長一致で BT 系統に解決し、出現数を数える。
    resolved_counts: Counter[str] = Counter()
    node_resolved: dict[str, str] = {}
    for nid, node in graph.nodes.items():
        kid = node.keito_id
        anchor = _longest_prefix_match(kid, anchors) if kid and kid != OTHER_ID else None
        node_resolved[nid] = anchor or ""
        if anchor:
            resolved_counts[anchor] += 1

    # 2nd pass: 上位 top_n を主要系統に採用。
    majors = [kid for kid, _ in resolved_counts.most_common(top_n)]
    majors_by_len = sorted(majors, key=len, reverse=True)
    major_set = set(majors)

    master: dict[str, dict[str, str]] = {}
    for i, kid in enumerate(majors):
        master[kid] = {
            "name": keito_names.get(kid, kid),
            "color": PALETTE[i % len(PALETTE)],
        }
    master[OTHER_ID] = {"name": OTHER_LABEL, "color": OTHER_COLOR}

    # 3rd pass: ノードの keito_id を「所属する主要系統」に正規化。
    #   まず解決済み系統が主要系統ならそれ。違えば、元 keito_id を主要系統アンカーへ
    #   最長一致で丸める (上位系統に寄せる)。当たらなければ "other"。
    for nid, node in graph.nodes.items():
        r = node_resolved.get(nid, "")
        if r and r in major_set:
            node.keito_id = r
            continue
        kid = node.keito_id
        major = _longest_prefix_match(kid, majors_by_len) if kid and kid != OTHER_ID else None
        node.keito_id = major or OTHER_ID

    return master
