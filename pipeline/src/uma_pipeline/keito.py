"""系統マスタの生成。

BT (系統情報) は JV-VAN が既に分類済み (HansyokuNum → KeitoId/KeitoName)。
系統は多数あるため、全馬での出現数を集計し、上位 N 系統に固有色、それ以外は「その他」に丸める。

生成物: keito-master.json  ->  { keitoId: {name, color}, "other": {name, color} }
"""

from __future__ import annotations

from collections import Counter

from .graph import PedigreeGraph

# 主要系統に割り当てる固有色 (識別しやすい配色)。TODO: 実データの系統数を見て N と配色を確定。
PALETTE: list[str] = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
    "#9a6324", "#808000", "#000075", "#e6beff", "#aaffc3",
]
OTHER_COLOR = "#999999"
OTHER_LABEL = "その他"


def build_keito_master(
    graph: PedigreeGraph,
    keito_names: dict[str, str],
    top_n: int = len(PALETTE),
) -> dict[str, dict[str, str]]:
    """系統マスタ (keitoId -> {name, color}) を生成する。

    Args:
        graph: 構築済み血統 DAG (各ノードの keito_id を参照)。
        keito_names: keitoId -> 系統名 の対応 (BT レコードから収集)。
        top_n: 固有色を割り当てる上位系統数。

    TODO: ノードの keito_id 出現数を数え、上位 top_n に PALETTE を割り当て、
          残りは "other" に丸めた dict を返す。以下は骨子。
    """
    counts: Counter[str] = Counter(
        node.keito_id for node in graph.nodes.values() if node.keito_id
    )
    master: dict[str, dict[str, str]] = {}
    for i, (keito_id, _count) in enumerate(counts.most_common(top_n)):
        master[keito_id] = {
            "name": keito_names.get(keito_id, keito_id),
            "color": PALETTE[i % len(PALETTE)],
        }
    master["other"] = {"name": OTHER_LABEL, "color": OTHER_COLOR}
    return master
