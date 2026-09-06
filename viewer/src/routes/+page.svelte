<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import HorseSearch from '$lib/HorseSearch.svelte';
	import HorseDetail from '$lib/HorseDetail.svelte';
	import { fetchHorseGraph, fetchKeitoMaster, horseExists } from '$lib/data';
	import { createGraph, type GraphHandle } from '$lib/graph';
	import type { HorseNode, KeitoMaster } from '$lib/types';

	let container: HTMLDivElement;
	let handle: GraphHandle | null = null;
	let keito: KeitoMaster = {};
	let currentId = '';
	let status: 'idle' | 'loading' | 'ready' | 'error' = 'idle';
	let message = '';
	let toast = '';

	// 選択状態 (詳細パネル用)。中心とは独立。
	let selected: HorseNode | null = null;
	let selectedCenterable = false;
	let selectedChecking = false;

	// URL の ?horse= と現在の中心を同期する。
	$: urlHorse = $page.url.searchParams.get('horse') ?? '';
	$: if (urlHorse && urlHorse !== currentId && status !== 'loading') {
		void center(urlHorse);
	}

	$: selectedKeitoName = selected ? (keito[selected.keitoId]?.name ?? '') : '';
	$: selectedIsCenter = !!selected && selected.id === currentId;

	onMount(async () => {
		try {
			keito = await fetchKeitoMaster();
		} catch (e) {
			console.warn('系統マスタの取得に失敗:', e);
		}
		if (urlHorse) await center(urlHorse);
	});

	async function center(id: string) {
		status = 'loading';
		message = '';
		try {
			const graph = await fetchHorseGraph(id);
			if (graph === null) {
				// データが無い馬。現在の表示は保ったまま、そっと知らせる。
				status = handle ? 'ready' : 'idle';
				showToast('この馬の血統データはありません');
				return;
			}
			currentId = id;
			selected = null;
			if (!handle) {
				handle = await createGraph(container, graph, {
					keito,
					onSelect: (node) => selectNode(node)
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

	// ノードタップ = 選択 (中心は変えない)。詳細パネルを出し、中心にできるか確認する。
	async function selectNode(node: HorseNode) {
		selected = node;
		handle?.setSelected(node.id);
		if (node.id === currentId) {
			selectedCenterable = false; // すでに中心
			return;
		}
		selectedChecking = true;
		selectedCenterable = false;
		const exists = await horseExists(node.id);
		// 確認中に別のノードが選ばれていなければ反映
		if (selected && selected.id === node.id) {
			selectedCenterable = exists;
			selectedChecking = false;
		}
	}

	function closePanel() {
		selected = null;
		handle?.setSelected(null);
	}

	// 中心切り替えは URL 経由 (共有可能)。パネルのボタンからのみ呼ばれる。
	function centerOn(node: HorseNode) {
		void goto(`?horse=${encodeURIComponent(node.id)}`, { keepFocus: true, noScroll: true });
	}

	let toastTimer: ReturnType<typeof setTimeout> | undefined;
	function showToast(msg: string) {
		toast = msg;
		clearTimeout(toastTimer);
		toastTimer = setTimeout(() => (toast = ''), 2600);
	}

	function sizeToContainer() {
		if (handle && container) handle.resize(container.clientWidth, container.clientHeight);
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
		<h1>血統図</h1>
		<HorseSearch onSelect={(id) => goto(`?horse=${encodeURIComponent(id)}`)} />
	</header>

	<div class="graph" bind:this={container}></div>

	{#if status === 'idle'}
		<p class="overlay">馬を検索してください</p>
	{:else if status === 'loading'}
		<p class="overlay">読み込み中…</p>
	{:else if status === 'error'}
		<p class="overlay error">読み込みに失敗しました: {message}</p>
	{/if}

	{#if toast}
		<div class="toast">{toast}</div>
	{/if}

	{#if status === 'ready'}
		<button
			class="reset"
			class:with-panel={!!selected}
			on:click={() => handle?.resetView()}
			aria-label="アングルを戻す"
			title="アングルを戻す"
		>
			⟳ 正面に戻す
		</button>
	{/if}

	<HorseDetail
		node={selected}
		centerable={selectedCenterable}
		checking={selectedChecking}
		isCenter={selectedIsCenter}
		keitoName={selectedKeitoName}
		onCenter={centerOn}
		onClose={closePanel}
	/>
</div>

<style>
	:global(html),
	:global(body) {
		margin: 0;
		height: 100%;
		background: #000;
		color: #fff;
		font-family: system-ui, sans-serif;
		/* スマホでのブラウザ既定のタッチ挙動(ダブルタップズーム等)を抑制 */
		touch-action: none;
		overscroll-behavior: none;
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
		gap: 0.75rem;
		padding: calc(0.6rem + env(safe-area-inset-top)) 0.9rem 0.6rem;
		pointer-events: none;
	}
	header > :global(*) {
		pointer-events: auto;
	}
	h1 {
		font-size: 1rem;
		font-weight: 700;
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
		text-align: center;
	}
	.overlay.error {
		color: #f28b82;
	}
	.toast {
		position: fixed;
		left: 50%;
		bottom: calc(1.5rem + env(safe-area-inset-bottom));
		transform: translateX(-50%);
		z-index: 30;
		background: rgba(40, 40, 44, 0.96);
		color: #fff;
		padding: 0.7rem 1.1rem;
		border-radius: 999px;
		font-size: 0.9rem;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
	}
	.reset {
		position: fixed;
		right: calc(0.9rem + env(safe-area-inset-right));
		bottom: calc(0.9rem + env(safe-area-inset-bottom));
		z-index: 15;
		background: rgba(30, 30, 34, 0.92);
		color: #eee;
		border: 1px solid #444;
		border-radius: 999px;
		padding: 0.6rem 0.95rem;
		font-size: 0.9rem;
		cursor: pointer;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
		transition: bottom 0.2s ease;
	}
	/* 詳細パネル表示中はパネルの上に逃がす */
	.reset.with-panel {
		bottom: calc(11rem + env(safe-area-inset-bottom));
	}
</style>
