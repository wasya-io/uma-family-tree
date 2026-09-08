import { error, json } from '@sveltejs/kit';
import { CACHE_SEARCH, withEdgeCache } from '$lib/server/cache';
import type { RequestHandler } from './$types';

// GET /api/search?q=ゴール
// 馬名(漢字)/カナ/英字の部分一致で最大 20 件返す。
// 検索は LIKE で horses を引くため rows_read が重い。クエリ文字列ごとにエッジキャッシュ
// し (withEdgeCache)、同じ検索語の再アクセスで D1 に到達しないようにする。
export const GET: RequestHandler = async ({ url, platform, request }) => {
	const db = platform?.env?.DB;
	if (!db) throw error(500, 'D1 binding (DB) が見つかりません');

	return withEdgeCache(request, platform, async () => {
		const q = (url.searchParams.get('q') ?? '').trim();
		if (!q) return json([], { headers: { 'cache-control': CACHE_SEARCH } });

		const like = `%${q.replace(/[%_]/g, (m) => '\\' + m)}%`;
		const res = await db
			.prepare(
				`SELECT id, name, kana, eng FROM horses
         WHERE name LIKE ?1 ESCAPE '\\' OR kana LIKE ?1 ESCAPE '\\' OR eng LIKE ?1 ESCAPE '\\'
         LIMIT 20`
			)
			.bind(like)
			.all<{ id: string; name: string | null; kana: string | null; eng: string | null }>();

		const entries = (res.results ?? []).map((r) => ({
			id: r.id,
			name: r.name ?? '',
			kana: r.kana ?? '',
			eng: r.eng ?? ''
		}));
		return json(entries, { headers: { 'cache-control': CACHE_SEARCH } });
	});
};
