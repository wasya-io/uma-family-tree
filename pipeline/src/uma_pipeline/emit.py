"""D1 (SQLite) 投入用データの書き出し。

血統 DAG を「隣接リスト」として SQL に落とす:
  - horses      : 全ノード
  - edges       : 全親子エッジ
  - keito_master: 系統マスタ (色分け)

事前展開 (祖先M代+子孫L代の切り出し) は行わない。祖先/子孫の探索は
Pages Functions 側の再帰 CTE で動的に行う (viewer/db/schema.sql 参照)。

出力は 1 つの .sql ファイル。`wrangler d1 execute --file=xxx.sql` で投入できる。
大量 INSERT を高速化するためトランザクションで囲み、複数行 VALUES でまとめる。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .graph import PedigreeGraph

# 1 つの INSERT にまとめる行数 (D1/SQLite の変数上限に配慮しつつ大きめに)。
BATCH = 200


def _sql_str(v: str | None) -> str:
    """文字列を SQL リテラルに (シングルクオートをエスケープ)。None/空は '' に。"""
    if v is None:
        return "''"
    return "'" + v.replace("'", "''") + "'"


def _sql_int(v: int | None) -> str:
    return "NULL" if v is None else str(int(v))


def _batched(rows: list[str], table: str, columns: str, out) -> None:
    """rows (各要素は "(...)" の VALUES 文字列) を BATCH ごとに INSERT で書き出す。"""
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        out.write(f"INSERT INTO {table} {columns} VALUES\n")
        out.write(",\n".join(chunk))
        out.write(";\n")


def write_sql(
    graph: PedigreeGraph,
    keito_master: dict[str, dict[str, str]],
    out_path: Path,
) -> dict[str, int]:
    """horses/edges/keito_master の INSERT を 1 つの .sql に書き出す。件数を返す。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    horse_rows: list[str] = []
    for n in graph.nodes.values():
        horse_rows.append(
            "("
            + ", ".join(
                [
                    _sql_str(n.id),
                    _sql_str(n.ketto_num),
                    _sql_str(n.name),
                    _sql_str(n.kana),
                    _sql_str(n.eng),
                    _sql_str(n.sex),
                    _sql_str(n.color),
                    _sql_int(n.birth_year),
                    _sql_str(n.keito_id or "other"),
                ]
            )
            + ")"
        )

    edge_rows: list[str] = []
    seen_edges: set[tuple[str, str]] = set()
    for elist in graph.parents_of.values():
        for e in elist:
            key = (e.source, e.target)
            if key in seen_edges:
                continue  # PRIMARY KEY (parent_id, child_id) 重複を避ける
            seen_edges.add(key)
            edge_rows.append(
                "("
                + ", ".join([_sql_str(e.source), _sql_str(e.target), _sql_str(e.parent)])
                + ")"
            )

    keito_rows: list[str] = []
    for kid, info in keito_master.items():
        keito_rows.append(
            "("
            + ", ".join([_sql_str(kid), _sql_str(info.get("name")), _sql_str(info.get("color"))])
            + ")"
        )

    with open(out_path, "w", encoding="utf-8") as out:
        out.write("PRAGMA foreign_keys=OFF;\n")
        out.write("BEGIN TRANSACTION;\n")
        # 再投入を想定して既存データをクリア (スキーマは schema.sql で別途適用)。
        out.write("DELETE FROM edges;\n")
        out.write("DELETE FROM horses;\n")
        out.write("DELETE FROM keito_master;\n")
        _batched(horse_rows, "horses",
                 "(id, ketto_num, name, kana, eng, sex, color, birth_year, keito_id)", out)
        _batched(edge_rows, "edges", "(parent_id, child_id, parent)", out)
        _batched(keito_rows, "keito_master", "(keito_id, name, color)", out)
        out.write("COMMIT;\n")

    return {"horses": len(horse_rows), "edges": len(edge_rows), "keito": len(keito_rows)}
