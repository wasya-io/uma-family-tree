import adapter from '@sveltejs/adapter-cloudflare';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// Cloudflare Pages + Functions (D1 バインディング) 向けアダプタ。
		// API ルート (/api/...) はエッジで D1 を叩く。フロントは SPA として動く。
		adapter: adapter()
	}
};

export default config;
