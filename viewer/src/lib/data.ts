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

/** 馬ノードファイル (中心馬の祖先M代+子孫L代サブグラフ)。 */
export function fetchHorseGraph(kettoNum: string): Promise<HorseGraph> {
	return getJson<HorseGraph>(`horses/${kettoNum}.json`);
}

/** 全部盛りファイル (限定始祖の全子孫)。 */
export function fetchFullGraph(kettoNum: string): Promise<HorseGraph> {
	return getJson<HorseGraph>(`full/${kettoNum}.json`);
}

/** 系統マスタ (色分け用)。 */
export function fetchKeitoMaster(): Promise<KeitoMaster> {
	return getJson<KeitoMaster>('keito-master.json');
}

/** 検索インデックス。 */
export function fetchSearchIndex(): Promise<SearchEntry[]> {
	return getJson<SearchEntry[]>('search-index.json');
}
