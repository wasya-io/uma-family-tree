import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// 完全静的 SPA (ssr=false, prerender=true)。データは実行時に R2 から fetch。
		// 静的出力なので Cloudflare Pages にそのまま載る (wrangler 不要)。
		adapter: adapter({
			fallback: 'index.html' // ?horse= クエリを持つ SPA ルーティング用フォールバック
		})
	}
};

export default config;
