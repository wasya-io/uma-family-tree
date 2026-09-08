import { error, json } from '@sveltejs/kit';
import { CACHE_STATIC, withEdgeCache } from '$lib/server/cache';
import type { RequestHandler } from './$types';

// GET /api/exists/:id
// その馬が存在するかだけを軽量に返す ({exists:boolean})。
// 血統サブグラフ全体を計算する /api/horse とは違い 1 行読むだけなので高速。
export const GET: RequestHandler = async ({ params, platform, request }) => {
	const db = platform?.env?.DB;
	if (!db) throw error(500, 'D1 binding (DB) が見つかりません');
	return withEdgeCache(request, platform, async () => {
		const row = await db
			.prepare('SELECT 1 AS x FROM horses WHERE id = ?1 LIMIT 1')
			.bind(params.id)
			.first<{ x: number }>();
		return json({ exists: !!row }, { headers: { 'cache-control': CACHE_STATIC } });
	});
};
