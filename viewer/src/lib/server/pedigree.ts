// D1 (SQLite) に対する血統クエリ。Pages Functions (SvelteKit エンドポイント) から使う。
// 再帰 CTE で中心馬の祖先 M 代 + 子孫 L 代を取得し、viewer の HorseGraph 形式に整形する。

import type { D1Database } from '@cloudflare/workers-types';
import type { HorseGraph, HorseNode, PedigreeEdge } from '$lib/types';

export const DEFAULT_ANCESTOR_DEPTH = 5;
export const DEFAULT_DESCENDANT_DEPTH = 3;

interface HorseRow {
	id: string;
	ketto_num: string | null;
	name: string | null;
	kana: string | null;
	eng: string | null;
	sex: string | null;
	color: string | null;
	birth_year: number | null;
	keito_id: string | null;
}

interface EdgeRow {
	parent_id: string;
	child_id: string;
	parent: string;
}

interface GenRow {
	id: string;
	generation: number;
}

/**
 * 中心 centerId の誘導部分グラフ (祖先 ancDepth 代 + 子孫 descDepth 代) を返す。
 * 存在しない中心なら null。
 */
export async function fetchPedigree(
	db: D1Database,
	centerId: string,
	ancDepth = DEFAULT_ANCESTOR_DEPTH,
	descDepth = DEFAULT_DESCENDANT_DEPTH
): Promise<HorseGraph | null> {
	// 中心馬の存在確認。
	const center = await db
		.prepare('SELECT id FROM horses WHERE id = ?1')
		.bind(centerId)
		.first<{ id: string }>();
	if (!center) return null;

	// 世代マップ: 祖先(+n)と子孫(-n)を再帰CTEで集め、|generation| 最小を採用。
	// 中心=0。MIN(ABS(gen)) を符号付きで拾うため、min(depth) を方向別に取ってから合成する。
	const genStmt = db
		.prepare(
			`WITH RECURSIVE
       anc(id, depth) AS (
         SELECT ?1, 0
         UNION
         SELECT e.parent_id, anc.depth + 1
         FROM edges e JOIN anc ON e.child_id = anc.id
         WHERE anc.depth < ?2
       ),
       des(id, depth) AS (
         SELECT ?1, 0
         UNION
         SELECT e.child_id, des.depth + 1
         FROM edges e JOIN des ON e.parent_id = des.id
         WHERE des.depth < ?3
       ),
       -- 方向ごとに最短 depth を取る
       anc_min(id, d) AS (SELECT id, MIN(depth) FROM anc GROUP BY id),
       des_min(id, d) AS (SELECT id, MIN(depth) FROM des GROUP BY id)
       -- 合成: 中心=0、祖先=+d、子孫=-d。両方に出る場合は中心(0)のみ。
       SELECT id, 0 AS generation FROM anc_min WHERE id = ?1
       UNION
       SELECT id, d AS generation FROM anc_min WHERE id != ?1
       UNION
       SELECT id, -d AS generation FROM des_min WHERE id != ?1`
		)
		.bind(centerId, ancDepth, descDepth);

	const genRes = await genStmt.all<GenRow>();
	const genMap = new Map<string, number>();
	for (const r of genRes.results ?? []) {
		const g = r.generation;
		// 同一 id が祖先側/子孫側 両方に出たら |g| が小さい方 (中心に近い方) を採用。
		const cur = genMap.get(r.id);
		if (cur === undefined || Math.abs(g) < Math.abs(cur)) genMap.set(r.id, g);
	}
	if (!genMap.has(centerId)) genMap.set(centerId, 0);

	const ids = [...genMap.keys()];
	if (ids.length === 0) return { center: centerId, nodes: [], edges: [] };

	// ノード情報を取得 (IN 句)。id は "H"+数字で安全なのでプレースホルダ列挙。
	const placeholders = ids.map((_, i) => `?${i + 1}`).join(',');
	const horseRes = await db
		.prepare(`SELECT * FROM horses WHERE id IN (${placeholders})`)
		.bind(...ids)
		.all<HorseRow>();

	const nodes: HorseNode[] = (horseRes.results ?? []).map((h) => ({
		id: h.id,
		kettoNum: h.ketto_num ?? '',
		name: h.name ?? '',
		kana: h.kana ?? '',
		eng: h.eng ?? '',
		sex: h.sex ?? '',
		color: h.color ?? '',
		birthYear: h.birth_year ?? null,
		keitoId: h.keito_id ?? 'other',
		generation: genMap.get(h.id) ?? 0
	}));

	// 誘導部分グラフのエッジ (両端が id 集合に含まれるもの)。
	// 2 つの IN で同じ ?1..?N プレースホルダを再利用し、ids を 1 回だけバインドする
	// (バインド数と参照数を一致させる)。
	const edgeRes = await db
		.prepare(
			`SELECT parent_id, child_id, parent FROM edges
       WHERE parent_id IN (${placeholders}) AND child_id IN (${placeholders})`
		)
		.bind(...ids)
		.all<EdgeRow>();

	const edges: PedigreeEdge[] = (edgeRes.results ?? []).map((e) => ({
		source: e.parent_id,
		target: e.child_id,
		parent: e.parent === 'mother' ? 'mother' : 'father'
	}));

	return { center: centerId, nodes, edges };
}
