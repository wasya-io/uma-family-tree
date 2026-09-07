import { error, json } from '@sveltejs/kit';
import { fetchPedigree, DEFAULT_ANCESTOR_DEPTH, DEFAULT_DESCENDANT_DEPTH } from '$lib/server/pedigree';
import type { RequestHandler } from './$types';

// GET /api/horse/:id?anc=5&desc=1&full=1
// 中心馬 :id の祖先 anc 代 + 子孫 desc 代のサブグラフを返す。存在しなければ 404。
// full=1 で「代表的な子」への絞り込みを解除 (全子を返す。重い)。
// 子表示モードは anc=0&desc=3 で呼ぶ (祖先なし・子孫3代)。anc/desc は 0..8 にクランプ。
// 注意: 代表子への絞り込みは中心の直仔にのみ効くため、種牡馬を desc>=2 で辿ると孫以降が
// 急増しうる (サンデーサイレンス desc=3 で 5000 超)。深さ増加時の総数は呼び出し側で留意。
export const GET: RequestHandler = async ({ params, url, platform }) => {
	const db = platform?.env?.DB;
	if (!db) throw error(500, 'D1 binding (DB) が見つかりません');

	const id = params.id;
	const anc = clampDepth(url.searchParams.get('anc'), DEFAULT_ANCESTOR_DEPTH);
	const desc = clampDepth(url.searchParams.get('desc'), DEFAULT_DESCENDANT_DEPTH);
	const full = url.searchParams.get('full') === '1';

	const graph = await fetchPedigree(db, id, { ancDepth: anc, descDepth: desc, full });
	if (graph === null) throw error(404, 'not found');

	return json(graph, {
		headers: {
			// 同一馬の再表示を軽くしつつ、データ/ロジック更新後の陳腐化を短時間に抑える。
			// (長すぎると仕様変更後も古いレスポンスが残り続ける)
			'cache-control': 'public, max-age=300'
		}
	});
};

function clampDepth(v: string | null, fallback: number): number {
	const n = v == null ? fallback : parseInt(v, 10);
	if (Number.isNaN(n)) return fallback;
	return Math.min(8, Math.max(0, n));
}
