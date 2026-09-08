// API レスポンスのキャッシュ制御を一元管理する。
//
// 血統データは長期間更新しない前提。D1 の読み取り (rows_read) を無料枠に収めるため、
// Cloudflare のエッジキャッシュ (s-maxage) を積極的に効かせて D1 到達を減らす。
//
//   - max-age   : ブラウザキャッシュ。同一ユーザーの再アクセスに効く。
//   - s-maxage  : Cloudflare エッジ (CDN) キャッシュ。**全ユーザー横断で効き、D1 到達を最も減らす**。
//                 データ更新時は再デプロイでキャッシュを事実上リフレッシュできる
//                 (デプロイで新しいアセットハッシュ/関数になるため)。
//
// 更新頻度が低いので、静的データ系は長め (7 日) に設定する。データを更新したら
// 再デプロイし、必要なら Cloudflare ダッシュボードでキャッシュをパージする。

const DAY = 86400;
const WEEK = 7 * DAY;

/** 静的データ (馬・系統・メタ・存在確認・検索)。ブラウザ 1 時間 / エッジ 7 日。 */
export const CACHE_STATIC = `public, max-age=${DAY}, s-maxage=${WEEK}`;

/** 検索など、クエリ文字列ごとにキャッシュしたいもの。値は STATIC と同じ方針。 */
export const CACHE_SEARCH = `public, max-age=${DAY}, s-maxage=${WEEK}`;

/** JSON レスポンス用のヘッダーを作る。 */
export function cacheHeaders(value: string): Record<string, string> {
	return { 'cache-control': value };
}

// Pages Functions (/api/*) は動的パス扱いのため、Cache-Control の s-maxage を付けるだけでは
// Cloudflare のエッジキャッシュに載らない (「Cache Everything」の Cache Rule が別途必要)。
// ダッシュボード設定に依存せず確実にエッジキャッシュを効かせるため、Worker の Cache API
// (caches.default) を明示的に使う。ヒットすれば D1 に到達せずキャッシュから返す。
//
// - キャッシュキー = リクエスト URL (クエリ文字列込み)。
// - 保存はレスポンスの Cache-Control (s-maxage) に従う。
// - 保存は waitUntil でバックグラウンド実行し、レスポンスを遅らせない。
//
// platform が無い環境 (SSR ローカル等) では素通しする。

interface EdgeCachePlatform {
	caches?: { default: Cache };
	context?: { waitUntil(p: Promise<unknown>): void };
}

export async function withEdgeCache(
	request: Request,
	platform: EdgeCachePlatform | undefined,
	produce: () => Promise<Response>
): Promise<Response> {
	const cache = platform?.caches?.default;
	// GET 以外やキャッシュ非対応環境はそのまま。
	if (!cache || request.method !== 'GET') return produce();

	const cacheKey = new Request(request.url, { method: 'GET' });
	const hit = await cache.match(cacheKey);
	if (hit) return hit;

	const res = await produce();
	// 正常応答のみキャッシュ (エラーはキャッシュしない)。
	if (res.ok) {
		const toCache = res.clone();
		const put = Promise.resolve(cache.put(cacheKey, toCache)).catch(() => {});
		if (platform?.context?.waitUntil) platform.context.waitUntil(put);
		else await put;
	}
	return res;
}
