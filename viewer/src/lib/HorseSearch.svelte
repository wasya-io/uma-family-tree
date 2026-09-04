<script lang="ts">
	import { fetchSearchIndex } from './data';
	import type { SearchEntry } from './types';

	// 選択時に中心 KettoNum を親へ通知。
	export let onSelect: (kettoNum: string) => void;

	let query = '';
	let index: SearchEntry[] = [];
	let loaded = false;
	let error = '';

	async function ensureIndex() {
		if (loaded) return;
		try {
			index = await fetchSearchIndex();
			loaded = true;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	// 馬名 (漢字/カナ) + 英字のインクリメンタルサーチ (部分一致)。
	$: results = matchResults(query, index);

	function matchResults(q: string, entries: SearchEntry[]): SearchEntry[] {
		const t = q.trim().toLowerCase();
		if (!t) return [];
		return entries
			.filter(
				(e) =>
					(e.name && e.name.toLowerCase().includes(t)) ||
					(e.kana && e.kana.toLowerCase().includes(t)) ||
					(e.eng && e.eng.toLowerCase().includes(t))
			)
			.slice(0, 20);
	}

	function select(entry: SearchEntry) {
		query = entry.name || entry.kana || entry.eng;
		onSelect(entry.id);
	}
</script>

<div class="search">
	<input
		type="search"
		placeholder="馬名 (カナ / 英字) で検索"
		bind:value={query}
		on:focus={ensureIndex}
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
