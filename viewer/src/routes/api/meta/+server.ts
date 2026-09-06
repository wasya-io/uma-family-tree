import { error, json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

// GET /api/meta
// データセットのメタ情報 (key/value)。data_timestamp = データ基準時点 (YYYYMMDDhhmmss)。
export const GET: RequestHandler = async ({ platform }) => {
	const db = platform?.env?.DB;
	if (!db) throw error(500, 'D1 binding (DB) が見つかりません');

	const res = await db
		.prepare('SELECT key, value FROM meta')
		.all<{ key: string; value: string | null }>();

	const meta: Record<string, string> = {};
	for (const r of res.results ?? []) {
		if (r.value != null) meta[r.key] = r.value;
	}
	return json(meta, { headers: { 'cache-control': 'public, max-age=86400' } });
};
