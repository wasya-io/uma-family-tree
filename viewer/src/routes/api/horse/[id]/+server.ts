import { error, json } from '@sveltejs/kit';
import { fetchPedigree, DEFAULT_ANCESTOR_DEPTH, DEFAULT_DESCENDANT_DEPTH } from '$lib/server/pedigree';
import { CACHE_STATIC, withEdgeCache } from '$lib/server/cache';
import type { RequestHandler } from './$types';

// GET /api/horse/:id?anc=5&desc=1&full=1
// 中心馬 :id の祖先 anc 代 + 子孫 desc 代のサブグラフを返す。存在しなければ 404。
// full=1 で「代表的な子」への絞り込みを解除 (全子を返す。重い)。
// 子表示モードは anc=0&desc=3 で呼ぶ (祖先なし・子孫3代)。anc/desc は 0..8 にクランプ。
// 注意: 代表子への絞り込みは中心の直仔にのみ効くため、種牡馬を desc>=2 で辿ると孫以降が
// 急増しうる (サンデーサイレンス desc=3 で 5000 超)。深さ増加時の総数は呼び出し側で留意。
//
// レスポンスは Cache API でエッジキャッシュする (withEdgeCache)。同一 URL の再アクセスは
// D1 に到達せずキャッシュから返るため rows_read を大きく減らせる。
export const GET: RequestHandler = async ({ params, url, platform, request }) => {
	const db = platform?.env?.DB;
	if (!db) throw error(500, 'D1 binding (DB) が見つかりません');

	return withEdgeCache(request, platform, async () => {
		const id = params.id;
		const anc = clampDepth(url.searchParams.get('anc'), DEFAULT_ANCESTOR_DEPTH);
		const desc = clampDepth(url.searchParams.get('desc'), DEFAULT_DESCENDANT_DEPTH);
		const full = url.searchParams.get('full') === '1';

		const graph = await fetchPedigree(db, id, { ancDepth: anc, descDepth: desc, full });
		// 404 は Response で返す (withEdgeCache は非 ok をキャッシュしない)。
		// クライアント (fetchHorseGraph) は status===404 を null 扱いする。
		if (graph === null) return json({ message: 'not found' }, { status: 404 });

		return json(graph, { headers: { 'cache-control': CACHE_STATIC } });
	});
};

function clampDepth(v: string | null, fallback: number): number {
	const n = v == null ? fallback : parseInt(v, 10);
	if (Number.isNaN(n)) return fallback;
	return Math.min(8, Math.max(0, n));
}
