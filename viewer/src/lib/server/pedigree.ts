// D1 (SQLite) に対する血統クエリ。Pages Functions (SvelteKit エンドポイント) から使う。
// 再帰 CTE で中心馬の祖先 M 代 + 子孫 L 代を取得し、viewer の HorseGraph 形式に整形する。

import type { D1Database } from '@cloudflare/workers-types';
import type { HorseGraph, HorseNode, PedigreeEdge } from '$lib/types';

export const DEFAULT_ANCESTOR_DEPTH = 5;
// 子孫方向は世代ごとに掛け算で増える (種牡馬だと3代で1万超)。表示破綻を防ぐため
// デフォルトは 1 代のみ。もっと下流を見たいときは子ノードをタップして中心を移す。
export const DEFAULT_DESCENDANT_DEPTH = 1;
// 中心馬の直仔がこの数を超えたら「代表的な子」だけに絞る (full 指定で解除)。
export const CHILD_THRESHOLD = 40;
// 代表表示で残す中心馬の直仔の数。
export const REPRESENTATIVE_CHILDREN = 40;
// 子孫方向を 2 代目以降 (孫・ひ孫) に辿るとき、各親から残す子の数 (賞金上位)。
// 中心の直仔は REPRESENTATIVE_CHILDREN で別に絞る。孫以降を絞らないと種牡馬で
// ノードが爆発する (サンデーサイレンス desc=3 で 5000 超) ため、各親ごとに上位のみ辿る。
export const DESC_FANOUT = 8;

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
	earnings: number | null;
	wins: number | null;
}

interface EdgeRow {
	parent_id: string;
	child_id: string;
	parent: string;
}

export interface FetchOptions {
	ancDepth?: number;
	descDepth?: number;
	full?: boolean; // true なら代表的な子への絞り込みをしない
}

/**
 * 中心 centerId の誘導部分グラフ (祖先 ancDepth 代 + 子孫 descDepth 代) を返す。
 * 存在しない中心なら null。
 *
 * 子孫方向: 中心馬の直仔が CHILD_THRESHOLD を超える場合、full でなければ
 * 「代表的な子」= 子孫を持つ子を優先 → 生年新しい順 で上位 REPRESENTATIVE_CHILDREN に絞る。
 * 孫以降はその代表子からのみ辿る。meta.truncatedChildren / totalChildren に情報を返す。
 */
export async function fetchPedigree(
	db: D1Database,
	centerId: string,
	opts: FetchOptions = {}
): Promise<HorseGraph | null> {
	const ancDepth = opts.ancDepth ?? DEFAULT_ANCESTOR_DEPTH;
	const descDepth = opts.descDepth ?? DEFAULT_DESCENDANT_DEPTH;
	const full = opts.full ?? false;

	// 中心馬の存在確認。
	const center = await db
		.prepare('SELECT id FROM horses WHERE id = ?1')
		.bind(centerId)
		.first<{ id: string }>();
	if (!center) return null;

	// 直仔の総数を数える。
	const childCountRow = await db
		.prepare('SELECT COUNT(*) AS c FROM edges WHERE parent_id = ?1')
		.bind(centerId)
		.first<{ c: number }>();
	const totalChildren = childCountRow?.c ?? 0;

	// 中心の直仔を代表に絞るか。
	const truncate = !full && descDepth > 0 && totalChildren > CHILD_THRESHOLD;
	// 孫以降の枝分かれ (fanout) を各親上位 DESC_FANOUT に絞るか。
	// full でなく、かつ 2 代以上辿る場合に有効 (孫の爆発を防ぐ)。直仔数に依らない。
	const limitFanout = !full && descDepth >= 2;

	// 子孫探索の「起点となる子」集合を定める CTE。
	//  - 通常: 中心の全直仔。
	//  - 絞る場合: 代表的な子 (子孫を持つ子=edgesに親として登場 を優先、次に生年新しい順) 上位N。
	// seed_children(id) を des CTE の1代目として使う。
	// 代表的な子の選抜順:
	//  1. 獲得賞金 (平地本賞金累計) の多い順 … 「活躍した子孫」の最良の近似。
	//  2. 勝利数の多い順 … 賞金が同じ (0 など) の中での序列。
	//  3. 子孫を持つ子を優先 … 賞金・勝利が無い古馬でも、繁殖に上がった子を残す。
	//  4. 生年の新しい順、id … 最終的なタイブレーク。
	const seedChildrenCte = truncate
		? `seed_children(id) AS (
        SELECT e.child_id FROM edges e
        LEFT JOIN horses h ON h.id = e.child_id
        WHERE e.parent_id = ?1
        ORDER BY
          COALESCE(h.earnings, 0) DESC,
          COALESCE(h.wins, 0) DESC,
          (CASE WHEN EXISTS (SELECT 1 FROM edges e2 WHERE e2.parent_id = e.child_id) THEN 0 ELSE 1 END),
          COALESCE(h.birth_year, 0) DESC,
          e.child_id
        LIMIT ${REPRESENTATIVE_CHILDREN}
      )`
		: `seed_children(id) AS (
        SELECT e.child_id FROM edges e WHERE e.parent_id = ?1
      )`;

	// 誘導部分グラフの id 集合を SQL 内で完結して求める共通 CTE。
	// D1 は 1 クエリのバインドパラメータ上限が小さい (~100) ため、id を並べて IN する
	// 方式は使わず、再帰 CTE を JOIN して、バインドは centerId + 深さ の 3 個に抑える。
	// 子孫 (des) は seed_children を1代目にして、そこから descDepth まで辿る。
	// 孫以降の枝分かれ (fanout) を、各親の子のうち賞金上位 DESC_FANOUT に制限する CTE。
	//  - 非再帰なので window 関数 ROW_NUMBER を使える。再帰項からはこの rn 付きの
	//    子集合を JOIN するだけにして「各親から上位N」を実現する。
	//  - full (絞り込み無し) のときは全エッジを辿る (rn を無視)。
	// 中心の直仔は seed_children (別途 REPRESENTATIVE_CHILDREN に絞る) が担うので、
	// ranked_edges は 2 代目以降 (des.depth >= 1 からの展開) にのみ効かせる。
	const descStep = limitFanout
		? `SELECT re.child_id, des.depth + 1
         FROM ranked_edges re JOIN des ON re.parent_id = des.id
         WHERE des.depth < ?3 AND re.rn <= ${DESC_FANOUT}`
		: `SELECT e.child_id, des.depth + 1
         FROM edges e JOIN des ON e.parent_id = des.id
         WHERE des.depth < ?3`;

	const rankedEdgesCte = limitFanout
		? `ranked_edges(parent_id, child_id, rn) AS (
        SELECT e.parent_id, e.child_id,
          ROW_NUMBER() OVER (
            PARTITION BY e.parent_id
            ORDER BY COALESCE(h.earnings, 0) DESC, COALESCE(h.wins, 0) DESC,
                     COALESCE(h.birth_year, 0) DESC, e.child_id
          )
        FROM edges e LEFT JOIN horses h ON h.id = e.child_id
      ),`
		: '';

	const idsCte = `WITH RECURSIVE
    anc(id, depth) AS (
      SELECT ?1, 0
      UNION
      SELECT e.parent_id, anc.depth + 1
      FROM edges e JOIN anc ON e.child_id = anc.id
      WHERE anc.depth < ?2
    ),
    ${seedChildrenCte},
    ${rankedEdgesCte}
    des(id, depth) AS (
      SELECT id, 1 FROM seed_children
      UNION
      ${descStep}
    ),
    anc_min(id, d) AS (SELECT id, MIN(depth) FROM anc GROUP BY id),
    des_min(id, d) AS (SELECT id, MIN(depth) FROM des GROUP BY id),
    -- 中心=0、祖先=+d、子孫=-d。両方に出る場合は中心(0)を優先。
    gen(id, generation) AS (
      SELECT ?1, 0
      UNION
      SELECT id, d FROM anc_min WHERE id != ?1
      UNION
      SELECT id, -d FROM des_min WHERE id != ?1
    ),
    -- 同一 id が複数世代に出たら |generation| 最小を採用。
    ids(id, generation) AS (
      SELECT id, generation FROM gen
      WHERE ABS(generation) = (SELECT MIN(ABS(g2.generation)) FROM gen g2 WHERE g2.id = gen.id)
      GROUP BY id
    )`;

	// ノード: ids と horses を JOIN。
	const horseRes = await db
		.prepare(
			`${idsCte}
       SELECT h.*, ids.generation AS generation
       FROM ids JOIN horses h ON h.id = ids.id`
		)
		.bind(centerId, ancDepth, descDepth)
		.all<HorseRow & { generation: number }>();

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
		generation: h.generation ?? 0,
		earnings: h.earnings ?? 0,
		wins: h.wins ?? 0
	}));

	// エッジ: 両端が ids に含まれるものだけ。
	const edgeRes = await db
		.prepare(
			`${idsCte}
       SELECT e.parent_id, e.child_id, e.parent FROM edges e
       WHERE e.parent_id IN (SELECT id FROM ids) AND e.child_id IN (SELECT id FROM ids)`
		)
		.bind(centerId, ancDepth, descDepth)
		.all<EdgeRow>();

	const edges: PedigreeEdge[] = (edgeRes.results ?? []).map((e) => ({
		source: e.parent_id,
		target: e.child_id,
		parent: e.parent === 'mother' ? 'mother' : 'father'
	}));

	// 「代表子孫を辿ったとき実際に到達できる最大の子孫世代」を求める。
	// 子表示モードの世代スイッチャーを、データが存在する世代までに制限するために使う。
	//
	// まず今回のレスポンスから、実際に到達した最深の子孫世代を数える。
	//   reachedDepth < descDepth なら「これ以上辿っても子孫はいない」ことが確定する
	//     (要求した世代まで辿りきる前に枝が尽きた) → それが最大深さ。
	//   reachedDepth == descDepth なら「まだ先がある可能性」があるので、
	//     MAX_DESC(=3) まで軽いクエリ (深さの最大値のみ) で確認する。
	const MAX_DESC = 3;
	let reachedDepth = 0;
	for (const n of nodes) {
		if (n.generation < 0 && -n.generation > reachedDepth) reachedDepth = -n.generation;
	}
	let maxDescDepth = reachedDepth;
	if (reachedDepth >= descDepth && descDepth < MAX_DESC) {
		// 先がある可能性があるので MAX_DESC まで深さだけを辿って確認する。
		const seedCte = truncate
			? `seed_children(id) AS (
          SELECT e.child_id FROM edges e LEFT JOIN horses h ON h.id = e.child_id
          WHERE e.parent_id = ?1
          ORDER BY COALESCE(h.earnings,0) DESC, COALESCE(h.wins,0) DESC,
                   (CASE WHEN EXISTS (SELECT 1 FROM edges e2 WHERE e2.parent_id = e.child_id) THEN 0 ELSE 1 END),
                   COALESCE(h.birth_year,0) DESC, e.child_id
          LIMIT ${REPRESENTATIVE_CHILDREN}
        )`
			: `seed_children(id) AS (SELECT e.child_id FROM edges e WHERE e.parent_id = ?1)`;
		const rankedCte = `ranked_edges(parent_id, child_id, rn) AS (
        SELECT e.parent_id, e.child_id,
          ROW_NUMBER() OVER (
            PARTITION BY e.parent_id
            ORDER BY COALESCE(h.earnings,0) DESC, COALESCE(h.wins,0) DESC,
                     COALESCE(h.birth_year,0) DESC, e.child_id
          )
        FROM edges e LEFT JOIN horses h ON h.id = e.child_id
      ),`;
		const depthRow = await db
			.prepare(
				`WITH RECURSIVE
         ${seedCte},
         ${rankedCte}
         des(id, depth) AS (
           SELECT id, 1 FROM seed_children
           UNION
           SELECT re.child_id, des.depth + 1
           FROM ranked_edges re JOIN des ON re.parent_id = des.id
           WHERE des.depth < ?2 AND re.rn <= ${DESC_FANOUT}
         )
         SELECT COALESCE(MAX(depth), 0) AS d FROM des`
			)
			.bind(centerId, MAX_DESC)
			.first<{ d: number }>();
		maxDescDepth = depthRow?.d ?? reachedDepth;
	}

	return {
		center: centerId,
		nodes,
		edges,
		meta: { truncatedChildren: truncate, totalChildren, maxDescDepth }
	};
}
