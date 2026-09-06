<script lang="ts">
	import { searchHorses } from './data';
	import type { SearchEntry } from './types';

	// 選択時にノード id を親へ通知。
	export let onSelect: (id: string) => void;

	let query = '';
	let results: SearchEntry[] = [];
	let error = '';
	let seq = 0; // 応答順序の入れ替わり防止

	// 入力のたびにサーバ検索 (D1)。簡易デバウンス。
	let debounce: ReturnType<typeof setTimeout> | undefined;
	function onInput() {
		clearTimeout(debounce);
		const q = query;
		debounce = setTimeout(() => void run(q), 180);
	}

	async function run(q: string) {
		const my = ++seq;
		error = '';
		try {
			const r = await searchHorses(q);
			if (my === seq) results = r; // 最新のリクエストだけ反映
		} catch (e) {
			if (my === seq) error = e instanceof Error ? e.message : String(e);
		}
	}

	function select(entry: SearchEntry) {
		query = entry.name || entry.kana || entry.eng;
		results = [];
		onSelect(entry.id);
	}
</script>

<div class="search">
	<input
		type="search"
		placeholder="馬名で検索"
		bind:value={query}
		on:input={onInput}
		aria-label="馬名で検索"
	/>
	{#if error}
		<p class="error">{error}</p>
	{:else if results.length > 0}
		<ul>
			{#each results as r (r.id)}
				<li>
					<button type="button" on:click={() => select(r)}>
						{r.name || r.kana}{#if r.eng}<span class="eng"> {r.eng}</span>{/if}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.search {
		position: relative;
		width: 320px;
		max-width: 90vw;
	}
	input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		border-radius: 6px;
		border: 1px solid #444;
		background: rgba(20, 20, 20, 0.9);
		color: #fff;
		font-size: 0.95rem;
	}
	ul {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
		position: absolute;
		width: 100%;
		max-height: 50vh;
		overflow-y: auto;
		background: rgba(20, 20, 20, 0.97);
		border: 1px solid #444;
		border-radius: 6px;
	}
	li button {
		display: block;
		width: 100%;
		text-align: left;
		padding: 0.4rem 0.75rem;
		background: none;
		border: none;
		color: #eee;
		cursor: pointer;
	}
	li button:hover {
		background: #2a2a2a;
	}
	.eng {
		color: #999;
		font-size: 0.85em;
	}
	.error {
		color: #f28b82;
		font-size: 0.85rem;
	}
</style>
