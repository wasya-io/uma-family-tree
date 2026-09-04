<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import HorseSearch from '$lib/HorseSearch.svelte';
	import { fetchHorseGraph, fetchKeitoMaster } from '$lib/data';
	import { createGraph, type GraphHandle } from '$lib/graph';
	import type { KeitoMaster } from '$lib/types';

	let container: HTMLDivElement;
	let handle: GraphHandle | null = null;
	let keito: KeitoMaster = {};
	let currentId = '';
	let status: 'idle' | 'loading' | 'ready' | 'error' = 'idle';
	let message = '';

	// URL の ?horse= と現在の中心を同期する。
	$: urlHorse = $page.url.searchParams.get('horse') ?? '';
	$: if (urlHorse && urlHorse !== currentId && status !== 'loading') {
		void center(urlHorse);
	}

	onMount(async () => {
		try {
			keito = await fetchKeitoMaster();
		} catch (e) {
			// 系統マスタが無くても描画は続行 (色はフォールバック)。
			console.warn('系統マスタの取得に失敗:', e);
		}
		// 初期表示: URL 指定があればそれを、なければ何も描かず検索待ち。
		if (urlHorse) await center(urlHorse);
	});

	async function center(kettoNum: string) {
		status = 'loading';
		message = '';
		try {
			const graph = await fetchHorseGraph(kettoNum);
			currentId = kettoNum;
			if (!handle) {
				handle = await createGraph(container, graph, {
					keito,
					onCenterChange: (id) => navigateTo(id)
				});
				sizeToContainer();
			} else {
				handle.update(graph);
			}
			status = 'ready';
		} catch (e) {
			status = 'error';
			message = e instanceof Error ? e.message : String(e);
		}
	}

	// 中心切り替えは URL 経由で行い、共有可能な状態を保つ。
	function navigateTo(kettoNum: string) {
		void goto(`?horse=${encodeURIComponent(kettoNum)}`, { keepFocus: true, noScroll: true });
	}

	function sizeToContainer() {
		if (handle && container) {
			handle.resize(container.clientWidth, container.clientHeight);
		}
	}

	onMount(() => {
		const onResize = () => sizeToContainer();
		window.addEventListener('resize', onResize);
		return () => {
			window.removeEventListener('resize', onResize);
			handle?.destroy();
		};
	});
</script>

<div class="app">
	<header>
		<h1>血統図ビューア</h1>
		<HorseSearch onSelect={navigateTo} />
	</header>

	<div class="graph" bind:this={container}></div>

	{#if status === 'idle'}
		<p class="overlay">馬を検索して中心に指定してください。</p>
	{:else if status === 'loading'}
		<p class="overlay">読み込み中…</p>
	{:else if status === 'error'}
		<p class="overlay error">読み込みに失敗しました: {message}</p>
	{/if}
</div>

<style>
	:global(body) {
		margin: 0;
		background: #000;
		color: #fff;
		font-family: system-ui, sans-serif;
	}
	.app {
		position: fixed;
		inset: 0;
		overflow: hidden;
	}
	header {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 1rem;
		pointer-events: none;
	}
	header > :global(*) {
		pointer-events: auto;
	}
	h1 {
		font-size: 1rem;
		font-weight: 600;
		margin: 0;
		white-space: nowrap;
	}
	.graph {
		position: absolute;
		inset: 0;
	}
	.overlay {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		z-index: 5;
		color: #aaa;
	}
	.overlay.error {
		color: #f28b82;
	}
</style>
