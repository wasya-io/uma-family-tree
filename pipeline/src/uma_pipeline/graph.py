"""血統 DAG の構築。

`records.ParsedData` を入力に、以下を構築する:

- ノード: 馬 (一意キーは KettoNum。KettoNum を持たない繁殖のみの馬は HansyokuNum 由来の
  代替 id を割り当てる — §未確定、下記 normalize_id 参照)。
- エッジ: 親 → 子 の有向辺 (parent="father"|"mother")。
- 逆引き: 子孫方向を辿るための「親 → 子リスト」インデックス。

血統は DAG (インブリードで同一祖先が複数箇所に登場するが 1 ノードに集約) として構築する。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .records import ParsedData


@dataclass
class Node:
    id: str                       # 一意キー (原則 KettoNum)
    name: str = ""
    kana: str = ""
    eng: str = ""
    sex: str = ""                 # デコード済み日本語ラベル
    color: str = ""               # デコード済み毛色ラベル
    birth_year: int | None = None
    keito_id: str = ""            # 系統ID (色分けキー)


@dataclass
class Edge:
    source: str                   # 親ノード id
    target: str                   # 子ノード id
    parent: str                   # "father" | "mother"


@dataclass
class PedigreeGraph:
    """血統 DAG 全体。ここから各馬のサブグラフを切り出す。"""

    nodes: dict[str, Node] = field(default_factory=dict)
    # 子 id -> その親エッジ (最大2本: father / mother)
    parents_of: dict[str, list[Edge]] = field(default_factory=dict)
    # 親 id -> その子エッジ (子孫方向の逆引き)
    children_of: dict[str, list[Edge]] = field(default_factory=dict)

    def ancestors(self, root_id: str, depth: int) -> set[str]:
        """root から祖先方向に depth 代ぶんのノード id を集める (BFS)。TODO: 実装。"""
        raise NotImplementedError

    def descendants(self, root_id: str, depth: int) -> set[str]:
        """root から子孫方向に depth 代ぶんのノード id を集める (BFS)。TODO: 実装。"""
        raise NotImplementedError


def normalize_id(*, ketto_num: str, hansyoku_num: str) -> str:
    """ノードの一意 id を決める。

    原則 KettoNum を使う。KettoNum を持たない繁殖のみの馬 (古い始祖等) は
    HansyokuNum 由来の代替 id を割り当てる。

    TODO: 代替 id の規約を確定する (例: "H:" + hansyoku_num のようなプレフィックス方式)。
    """
    raise NotImplementedError


def build_graph(data: ParsedData) -> PedigreeGraph:
    """パース結果から血統 DAG を構築する。

    TODO: 実装。
      1. HN の親ポインタ (father/mother の HansyokuNum) を辿って親子エッジを張る
      2. HansyokuNum <-> KettoNum の対応を解決してノード id を正規化 (normalize_id)
      3. BT (系統) を各ノードの keito_id にひも付け
      4. SexCD/KeiroCD を codes.py でデコード
      5. children_of (逆引き) を構築して子孫方向の探索を可能にする
    """
    raise NotImplementedError
