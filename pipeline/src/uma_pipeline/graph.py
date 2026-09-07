"""血統 DAG の構築。

`records.ParsedData` を入力に、以下を構築する:

- ノード: 馬。**一意キーは繁殖登録番号 (HansyokuNum)**。理由は下記。
- エッジ: 親 → 子 の有向辺 (parent="father"|"mother")。
- 逆引き: 子孫方向を辿るための「親 → 子リスト」インデックス。

血統は DAG (インブリードで同一祖先が複数箇所に登場するが 1 ノードに集約) として構築する。

## ノード一意キーに HansyokuNum を使う理由

血統の親子リンクは HN (繁殖馬マスタ) の FNum/MNum (繁殖登録番号) で表現される。
実データで父/母リンクは HansyokuNum に対して 100% 整合する。一方 KettoNum (血統登録番号)
は「競走馬として登録された馬」にしか無く、古い始祖や輸入繁殖馬には無い。よって血統グラフを
欠損なく張れる普遍キーは HansyokuNum。ノード id は "H" + HansyokuNum とする。

競走馬として走った馬は KettoNum も持つ (HN レコードに併記)。KettoNum は検索/URL 共有の
補助キーとしてノード属性に持たせ、UM (競走馬マスタ) の表示情報 (馬名/性別/毛色/生年) で
ノードを強化する。

## 系統 (KeitoId) の扱い

BT は系統の「代表繁殖馬」にのみ系統レコードを持つ (実データで 92 件)。KeitoId は
「2桁ごとに系譜を表現する」階層 ID (例: 01080201010201 = サンデーサイレンス系)。
各馬の系統色は、父方をさかのぼって最初に見つかる KeitoId を継承させることで決める
(assign_keito 参照)。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from . import codes
from .records import ParsedData


def node_id(hansyoku_num: str) -> str:
    """繁殖登録番号からノード id を作る。"""
    return "H" + hansyoku_num


@dataclass
class Node:
    id: str                       # 一意キー ("H" + HansyokuNum)
    hansyoku_num: str = ""
    ketto_num: str = ""           # 競走馬なら血統登録番号 (検索/URL 用)。無ければ空。
    name: str = ""
    kana: str = ""
    eng: str = ""
    sex: str = ""                 # デコード済み日本語ラベル
    color: str = ""               # デコード済み毛色ラベル
    birth_year: int | None = None
    keito_id: str = ""            # 系統ID (色分けキー)
    earnings: int = 0             # 平地本賞金累計 (UM 由来。代表子孫の優先に使う)
    wins: int = 0                 # 総合1着回数 (UM 由来)


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

    def add_edge(self, parent_id: str, child_id: str, parent: str) -> None:
        e = Edge(source=parent_id, target=child_id, parent=parent)
        self.parents_of.setdefault(child_id, []).append(e)
        self.children_of.setdefault(parent_id, []).append(e)

    def ancestors(self, root_id: str, depth: int) -> set[str]:
        """root から祖先方向 (親) に depth 代ぶんのノード id を集める (BFS)。root 自身も含む。"""
        return self._bfs(root_id, depth, self.parents_of)

    def descendants(self, root_id: str, depth: int) -> set[str]:
        """root から子孫方向 (子) に depth 代ぶんのノード id を集める (BFS)。root 自身も含む。"""
        return self._bfs(root_id, depth, self.children_of)

    def _bfs(self, root_id: str, depth: int, adj: dict[str, list[Edge]]) -> set[str]:
        seen = {root_id}
        frontier = deque([(root_id, 0)])
        while frontier:
            cur, d = frontier.popleft()
            if d >= depth:
                continue
            for e in adj.get(cur, ()):
                nxt = e.target if adj is self.children_of else e.source
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append((nxt, d + 1))
        return seen


def build_graph(data: ParsedData) -> PedigreeGraph:
    """パース結果から血統 DAG を構築する。

    手順:
      1. HN (繁殖馬) を全てノード化 (id = "H"+HansyokuNum)。親ポインタでエッジを張る。
      2. UM (競走馬) の表示情報で対応ノードを強化 (KettoNum 経由でひも付け)。
         UM にしか無い馬 (繁殖入りしていない競走馬) は UM 単体でノード化。
      3. BT の KeitoId をノードにひも付け、父方継承で全ノードに系統を伝播。
      4. SexCD/KeiroCD を日本語ラベルにデコード。
    """
    g = PedigreeGraph()

    # --- 1. HN をノード化 ---
    for h in data.hansyoku.values():
        nid = node_id(h.hansyoku_num)
        g.nodes[nid] = Node(
            id=nid,
            hansyoku_num=h.hansyoku_num,
            ketto_num=h.ketto_num if _valid(h.ketto_num) else "",
            name=h.name,
            kana=h.kana,
            eng=h.eng,
            sex=codes.decode_sex(h.sex_cd),
            color=codes.decode_keiro(h.keiro_cd),
            birth_year=h.birth_year,
        )

    # --- 1b. 親エッジを張る ---
    for h in data.hansyoku.values():
        child = node_id(h.hansyoku_num)
        if _valid(h.father_hansyoku_num) and node_id(h.father_hansyoku_num) in g.nodes:
            g.add_edge(node_id(h.father_hansyoku_num), child, "father")
        if _valid(h.mother_hansyoku_num) and node_id(h.mother_hansyoku_num) in g.nodes:
            g.add_edge(node_id(h.mother_hansyoku_num), child, "mother")

    # --- 2. UM で強化 (KettoNum -> ノード) ---
    #   HN 側に KettoNum があるノードで索引を作り、UM の表示情報で上書き強化する。
    ketto_to_node: dict[str, Node] = {
        n.ketto_num: n for n in g.nodes.values() if n.ketto_num
    }
    for u in data.uma.values():
        n = ketto_to_node.get(u.ketto_num)
        if n is not None:
            # 競走馬マスタの方が表示情報が整っているので優先。
            n.name = u.name or n.name
            n.kana = u.kana or n.kana
            n.eng = u.eng or n.eng
            if u.sex_cd:
                n.sex = codes.decode_sex(u.sex_cd)
            if u.keiro_cd:
                n.color = codes.decode_keiro(u.keiro_cd)
            n.birth_year = u.birth_year or n.birth_year
            # 実績 (代表子孫の優先表示に使う)。UM にしか無いので UM から取る。
            n.earnings = u.earnings
            n.wins = u.wins

    # --- 3. 系統 (KeitoId) をひも付け、父方継承で伝播 ---
    for kt in data.keito.values():
        nid = node_id(kt.hansyoku_num)
        n = g.nodes.get(nid)
        if n is not None and kt.keito_id:
            n.keito_id = kt.keito_id
    _propagate_keito(g)

    return g


def _valid(num: str) -> bool:
    """繁殖/血統登録番号が実在値か (空・全ゼロは無効)。"""
    return bool(num) and set(num) != {"0"}


def _propagate_keito(g: PedigreeGraph) -> None:
    """KeitoId を持たないノードに、父方をさかのぼって最初に見つかる KeitoId を継承させる。

    父方リンクを上向きに辿る。循環は無い前提 (DAG) だが安全のため訪問済みを管理。
    """
    def father_of(nid: str) -> str | None:
        for e in g.parents_of.get(nid, ()):
            if e.parent == "father":
                return e.source
        return None

    cache: dict[str, str] = {}

    def resolve(nid: str) -> str:
        if nid in cache:
            return cache[nid]
        chain = []
        cur: str | None = nid
        result = ""
        seen = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            node = g.nodes.get(cur)
            if node is None:
                break
            if node.keito_id:
                result = node.keito_id
                break
            if cur in cache:
                result = cache[cur]
                break
            chain.append(cur)
            cur = father_of(cur)
        for c in chain:
            cache[c] = result
        return result

    for nid, node in g.nodes.items():
        if not node.keito_id:
            node.keito_id = resolve(nid)
