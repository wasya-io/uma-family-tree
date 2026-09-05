// R2 (または static) から配信 JSON を取得するデータクライアント。
// ビューアは組み立て処理を持たず、ここで取得したデータをそのまま描画する。

import { env } from '$env/dynamic/public';
import type { HorseGraph, KeitoMaster, SearchEntry } from './types';

// PUBLIC_DATA_BASE_URL は R2 配信のベース URL。未設定でも壊れないよう dynamic を使う。
const BASE = env.PUBLIC_DATA_BASE_URL?.replace(/\/$/, '') ?? '';

async function getJson<T>(path: string): Promise<T> {
	const res = await fetch(`${BASE}/${path}`);
	if (!res.ok) {
		throw new Error(`データ取得に失敗: ${path} (${res.status})`);
	}
	return (await res.json()) as T;
}

/**
 * 馬ノードファイルを取得。存在しない (404) 場合は null を返す (エラーにしない)。
 * データの無い馬を中心にしようとしても操作不能にならないようにするため。
 */
export async function fetchHorseGraph(id: string): Promise<HorseGraph | null> {
	const res = await fetch(`${BASE}/horses/${id}.json`);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`データ取得に失敗: horses/${id}.json (${res.status})`);
	return (await res.json()) as HorseGraph;
}

/** 馬ノードファイルが存在するか (中心にできるかの判定用)。 */
export async function horseExists(id: string): Promise<boolean> {
	try {
		// HEAD が使えれば軽い。static/R2 とも HEAD をサポートする。
		const res = await fetch(`${BASE}/horses/${id}.json`, { method: 'HEAD' });
		return res.ok;
	} catch {
		return false;
	}
}

/** 全部盛りファイル (限定始祖の全子孫)。 */
export function fetchFullGraph(id: string): Promise<HorseGraph> {
	return getJson<HorseGraph>(`full/${id}.json`);
}

/** 系統マスタ (色分け用)。 */
export function fetchKeitoMaster(): Promise<KeitoMaster> {
	return getJson<KeitoMaster>('keito-master.json');
}

/** 検索インデックス。 */
export function fetchSearchIndex(): Promise<SearchEntry[]> {
	return getJson<SearchEntry[]>('search-index.json');
}
