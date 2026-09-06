// フロントは SPA (クライアント描画)。API ルート (/api/*) は Pages Functions で
// 動的に D1 を叩くため、全体プリレンダーはしない。
export const ssr = false;
export const prerender = false;
