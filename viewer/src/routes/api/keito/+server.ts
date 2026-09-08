import { error, json } from '@sveltejs/kit';
import { CACHE_STATIC, withEdgeCache } from '$lib/server/cache';
import type { RequestHandler } from './$types';
import type { KeitoMaster } from '$lib/types';

// GET /api/keito
// 系統マスタ (keitoId -> {name, color}) を返す。件数は少数 (数十) なので一括で返す。
export const GET: RequestHandler = async ({ platform, request }) => {
	const db = platform?.env?.DB;
	if (!db) throw error(500, 'D1 binding (DB) が見つかりません');

	return withEdgeCache(request, platform, async () => {
		const res = await db
			.prepare('SELECT keito_id, name, color FROM keito_master')
			.all<{ keito_id: string; name: string | null; color: string | null }>();

		const master: KeitoMaster = {};
		for (const r of res.results ?? []) {
			master[r.keito_id] = { name: r.name ?? r.keito_id, color: r.color ?? '#999999' };
		}
		return json(master, { headers: { 'cache-control': CACHE_STATIC } });
	});
};
