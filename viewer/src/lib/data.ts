// 同一オリジンの API (Pages Functions + D1) からデータを取得するクライアント。
// 以前は R2 の静的 JSON を fetch していたが、D1 化に伴い API 経由に変更。

import type { HorseGraph, KeitoMaster, SearchEntry } from './types';

/**
 * 馬の血統サブグラフを取得。存在しない (404) 場合は null を返す (エラーにしない)。
 * full=true で「代表的な子」への絞り込みを解除し全子を取得する (重い)。
 */
export async function fetchHorseGraph(id: string, full = false): Promise<HorseGraph | null> {
	const qs = full ? '?full=1' : '';
	const res = await fetch(`/api/horse/${encodeURIComponent(id)}${qs}`);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`データ取得に失敗: /api/horse/${id} (${res.status})`);
	return (await res.json()) as HorseGraph;
}

/**
 * 馬が存在するか (中心にできるかの判定用)。
 * /api/exists は 1 行読むだけなので、血統サブグラフ全体を計算する /api/horse を
 * HEAD で叩いていた旧実装より圧倒的に速い (サンデーサイレンス級でも一瞬)。
 */
export async function horseExists(id: string): Promise<boolean> {
	try {
		const res = await fetch(`/api/exists/${encodeURIComponent(id)}`);
		if (!res.ok) return false;
		const data = (await res.json()) as { exists: boolean };
		return data.exists;
	} catch {
		return false;
	}
}

/** 系統マスタ (色分け用)。 */
export async function fetchKeitoMaster(): Promise<KeitoMaster> {
	const res = await fetch('/api/keito');
	if (!res.ok) throw new Error(`系統マスタ取得に失敗 (${res.status})`);
	return (await res.json()) as KeitoMaster;
}

/** 馬名 (漢字/カナ/英字) の部分一致検索。最大 20 件。 */
export async function searchHorses(q: string): Promise<SearchEntry[]> {
	const t = q.trim();
	if (!t) return [];
	const res = await fetch(`/api/search?q=${encodeURIComponent(t)}`);
	if (!res.ok) throw new Error(`検索に失敗 (${res.status})`);
	return (await res.json()) as SearchEntry[];
}
