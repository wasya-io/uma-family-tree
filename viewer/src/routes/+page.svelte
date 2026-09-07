<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import HorseSearch from '$lib/HorseSearch.svelte';
	import HorseDetail from '$lib/HorseDetail.svelte';
	import { fetchHorseGraph, fetchKeitoMaster, fetchMeta, horseExists } from '$lib/data';
	import { createGraph, type GraphHandle } from '$lib/graph';
	import type { HorseNode, KeitoMaster } from '$lib/types';

	let container: HTMLDivElement;
	let handle: GraphHandle | null = null;
	let keito: KeitoMaster = {};
	// 系統マスタの読み込み完了を待つための Promise。グラフ生成 (色分け) 前に必ず解決させ、
	// 「keito が空のままグラフが作られて全ノードがグレーになる」競合を防ぐ。
	let keitoReady: Promise<void> | null = null;
	let currentId = '';
	let centerName = ''; // 中心馬の名前 (タイトル表示用)
	let dataDate = ''; // データ基準日 (フッター表示用, YYYY年M月D日)
	let status: 'idle' | 'loading' | 'ready' | 'error' = 'idle';
	let message = '';
	let toast = '';

	// 免責事項。初回は未確認 → フッターにガイドを出す。文面はダイアログで表示。
	const DISCLAIMER_KEY = 'uft.disclaimer.ack.v1';
	let disclaimerAck = true; // SSR/初期は true にしておき onMount で確定 (チラつき防止)
	let showDisclaimer = false;

	// 操作ガイド。初回のみ画面下部に軽く表示 → 数秒で自動的に消える / タップで閉じる。
	const GUIDE_KEY = 'uft.guide.seen.v1';
	let showGuide = false;
	let guideTimer: ReturnType<typeof setTimeout> | undefined;

	// 選択状態 (詳細パネル用)。中心とは独立。
	let selected: HorseNode | null = null;
	let selectedCenterable = false;
	let selectedChecking = false;

	// 子孫の間引き情報。代表的な子だけ表示中かどうか。
	let truncatedChildren = false;
	let totalChildren = 0;
	let showingAll = false; // 「すべて表示」中か
	let loadingAll = false;

	// 子表示モード。ON にすると祖先を消し、子孫を descGen 代まで展開する
	// (代表的な子孫=獲得賞金上位 を優先)。OFF は通常の祖先中心表示。
	let childMode = false;
	let descGen = 2; // 子孫の表示世代数 (1〜3)
	let maxDescDepth = 0; // データ上たどれる最大の子孫世代 (0=子もいない, 1=子まで, ...)
	const CHILD_ANC = 0; // 子モードの祖先代数 (祖先は消す)
	const NORMAL_ANC = 5; // 通常モードの祖先代数 (サーバ既定と同じ)
	const NORMAL_DESC = 1; // 通常モードの子孫代数

	// URL の ?horse= と現在の中心を同期する。
	$: urlHorse = $page.url.searchParams.get('horse') ?? '';
	$: if (urlHorse && urlHorse !== currentId && status !== 'loading') {
		void center(urlHorse);
	}

	$: selectedKeitoName = selected ? (keito[selected.keitoId]?.name ?? '') : '';
	$: selectedIsCenter = !!selected && selected.id === currentId;

	onMount(async () => {
		// 免責の確認状態を復元。?disclaimer=reset が付いていたらフラグを消して再表示
		// (開発中や「もう一度きちんと読みたい」とき用。URL からクエリは除去する)。
		try {
			const params = $page.url.searchParams;
			// ?disclaimer=reset / ?guide=reset で確認フラグを消して再表示 (開発/再確認用)。
			const disclaimerReset = params.get('disclaimer') === 'reset';
			const guideReset = params.get('guide') === 'reset';
			if (disclaimerReset) localStorage.removeItem(DISCLAIMER_KEY);
			if (guideReset) localStorage.removeItem(GUIDE_KEY);
			if (disclaimerReset || guideReset) {
				const url = new URL(window.location.href);
				url.searchParams.delete('disclaimer');
				url.searchParams.delete('guide');
				history.replaceState(history.state, '', url);
			}
			disclaimerAck = localStorage.getItem(DISCLAIMER_KEY) === '1';
			// 操作ガイド: 未確認なら表示し、8 秒後に自動で閉じる。
			if (localStorage.getItem(GUIDE_KEY) !== '1') {
				showGuide = true;
				guideTimer = setTimeout(dismissGuide, 8000);
			}
		} catch {
			disclaimerAck = false; // localStorage 不可の環境では毎回ガイドを出す
			showGuide = true; // 操作ガイドも同様に出す
		}

		await ensureKeito();
		try {
			const meta = await fetchMeta();
			dataDate = formatDataDate(meta.data_timestamp);
		} catch (e) {
			console.warn('メタ情報の取得に失敗:', e);
		}
		if (urlHorse) await center(urlHorse);
	});

	// YYYYMMDDhhmmss → "YYYY年M月D日" (時刻は省略)。
	function formatDataDate(ts: string | undefined): string {
		if (!ts || ts.length < 8) return '';
		const y = ts.slice(0, 4);
		const m = String(parseInt(ts.slice(4, 6), 10));
		const d = String(parseInt(ts.slice(6, 8), 10));
		return `${y}年${m}月${d}日`;
	}

	// 系統マスタを一度だけ読み込む。複数箇所 (onMount / center) から呼ばれても
	// 同じ Promise を共有し、二重取得と競合を避ける。
	function ensureKeito(): Promise<void> {
		if (!keitoReady) {
			keitoReady = fetchKeitoMaster()
				.then((k) => {
					keito = k;
				})
				.catch((e) => {
					console.warn('系統マスタの取得に失敗:', e);
				});
		}
		return keitoReady;
	}

	async function center(id: string, full = false) {
		status = 'loading';
		message = '';
		try {
			// 色分けに使う系統マスタを、グラフ生成より前に必ず用意する。
			await ensureKeito();
			// 表示モードで祖先/子孫の代数を切り替える。
			const anc = childMode ? CHILD_ANC : NORMAL_ANC;
			const desc = childMode ? descGen : NORMAL_DESC;
			const graph = await fetchHorseGraph(id, { full, anc, desc });
			if (graph === null) {
				// データが無い馬。現在の表示は保ったまま、そっと知らせる。
				status = handle ? 'ready' : 'idle';
				showToast('この馬の血統データはありません');
				return;
			}
			currentId = id;
			selected = null;
			// 中心馬の名前を取り出してタイトルに使う。
			const centerNode = graph.nodes.find((n) => n.id === graph.center);
			centerName = centerNode?.name || centerNode?.kana || centerNode?.eng || '';
			// 間引き情報を反映。
			truncatedChildren = graph.meta?.truncatedChildren ?? false;
			totalChildren = graph.meta?.totalChildren ?? 0;
			maxDescDepth = graph.meta?.maxDescDepth ?? 0;
			// 選択中の世代がデータ上たどれる範囲を超えていたら、実際の最大に合わせる
			// (スイッチャーのハイライトを実表示と一致させる)。最低 1。
			if (childMode && maxDescDepth >= 1 && descGen > maxDescDepth) descGen = maxDescDepth;
			showingAll = full;
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

	// 「すべて表示」: 現在の中心馬を絞り込み解除で取り直す (重い)。
	async function showAllChildren() {
		if (!currentId || loadingAll) return;
		loadingAll = true;
		try {
			await center(currentId, true);
		} finally {
			loadingAll = false;
		}
	}

	// 「代表表示に戻す」: 全表示から代表的な子だけの表示に戻す。
	async function showRepresentative() {
		if (!currentId || loadingAll) return;
		loadingAll = true;
		try {
			await center(currentId, false);
		} finally {
			loadingAll = false;
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

	// 子表示モードの ON/OFF を切り替えて再表示する。
	async function toggleChildMode() {
		if (!currentId || loadingAll) return;
		childMode = !childMode;
		showingAll = false; // モード切替時は代表表示に戻す
		await center(currentId, false);
	}

	// 子孫の表示世代数を変えて再表示する (子モード時のみ)。
	// データ上たどれない世代 (maxDescDepth 超) は選べない。
	async function changeDescGen(n: number) {
		if (!currentId || loadingAll || n === descGen) return;
		if (n > maxDescDepth) return; // データが無い世代は無視
		descGen = n;
		if (childMode) await center(currentId, false);
	}

	// 操作ガイドを閉じる (タップ / 自動タイマー)。以降は出さないよう記録する。
	function dismissGuide() {
		clearTimeout(guideTimer);
		showGuide = false;
		try {
			localStorage.setItem(GUIDE_KEY, '1');
		} catch {
			// localStorage 不可でも UI 上は閉じる
		}
	}

	function openDisclaimer() {
		showDisclaimer = true;
	}

	// ダイアログを閉じたら確認済みにする (フッターのガイドは以降出さない)。
	function closeDisclaimer() {
		showDisclaimer = false;
		disclaimerAck = true;
		try {
			localStorage.setItem(DISCLAIMER_KEY, '1');
		} catch {
			// localStorage 不可でも UI 上は閉じる
		}
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
			clearTimeout(guideTimer);
			handle?.destroy();
		};
	});
</script>

<svelte:head>
	<title>{centerName ? `${centerName} の血統図` : '血統図'}</title>
</svelte:head>

<div class="app">
	<header>
		<div class="title">
			<span class="app-name">血統図</span>
			{#if centerName}<span class="center-name">{centerName}</span>{/if}
		</div>
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

	{#if showGuide}
		<button type="button" class="guide" on:click={dismissGuide}>
			<span class="guide-row">👆 馬をタップで詳細</span>
			<span class="guide-row">🖐 1本指で回転 ・ 2本指でズーム</span>
			<span class="guide-dismiss">タップして閉じる</span>
		</button>
	{/if}

	{#if status === 'ready' && truncatedChildren && !showingAll}
		<div class="notice">
			<span>子が多いため代表的な子のみ表示中(全 {totalChildren} 頭)</span>
			<button on:click={showAllChildren} disabled={loadingAll}>
				{loadingAll ? '読み込み中…' : 'すべて表示'}
			</button>
		</div>
	{:else if status === 'ready' && showingAll && totalChildren > 40}
		<div class="notice">
			<span>すべての子を表示中(全 {totalChildren} 頭)</span>
			<button on:click={showRepresentative} disabled={loadingAll}>
				{loadingAll ? '読み込み中…' : '代表表示に戻す'}
			</button>
		</div>
	{/if}

	{#if status === 'ready'}
		<div class="mode-panel" class:with-panel={!!selected}>
			<button
				class="mode-toggle"
				class:on={childMode}
				on:click={toggleChildMode}
				disabled={loadingAll}
				title={childMode ? '祖先表示に戻す' : '子孫を見る'}
			>
				{childMode ? '👶 子表示中' : '👶 子を見る'}
			</button>
			{#if childMode}
				<div class="gen-wrap">
					<div class="gen-picker" role="group" aria-label="子孫の世代数">
						{#each [1, 2, 3] as g}
							<button
								class="gen"
								class:sel={descGen === g}
								on:click={() => changeDescGen(g)}
								disabled={loadingAll || g > maxDescDepth}
								title={g > maxDescDepth ? 'この世代のデータはありません' : `${g}代先まで表示`}
							>
								{g}代
							</button>
						{/each}
					</div>
					{#if maxDescDepth <= 1}
						<span class="gen-note">これ以上の世代のデータはありません</span>
					{:else if maxDescDepth < 3}
						<span class="gen-note">{maxDescDepth}代先までのデータがあります</span>
					{/if}
				</div>
			{/if}
		</div>

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

	{#if !selected}
		<footer class="data-footer">
			{#if !disclaimerAck}
				<button type="button" class="disclaimer-guide" on:click={openDisclaimer}>
					⚠ 本サイト利用上の注意事項をご確認ください
				</button>
			{/if}
			<div class="footer-line">
				{#if dataDate}<span>本サイトの血統データは {dataDate}時点のものです</span>{/if}
				<button type="button" class="disclaimer-link" on:click={openDisclaimer}>免責事項</button>
			</div>
		</footer>
	{/if}

	{#if showDisclaimer}
		<div
			class="disclaimer-backdrop"
			role="button"
			tabindex="-1"
			on:click={closeDisclaimer}
			on:keydown={(e) => e.key === 'Escape' && closeDisclaimer()}
		></div>
		<div class="disclaimer-modal" role="dialog" aria-modal="true" aria-label="免責事項・データについてのご注意">
			<h2>免責事項・データについてのご注意</h2>
			<p>
				本サイトは、JRA-VAN Data Lab. で取得した競走馬データをもとに血統を可視化する、個人が運営する非公式のサービスです。JRA・JRA-VAN その他の団体とは一切関係ありません。
			</p>
			<ul>
				<li>
					<strong>データの正確性を保証しません。</strong>
					表示している血統は、取得した生データを独自に加工・結合して生成したものです。加工処理の性質上、実際の血統と異なる場合や、欠落・誤りが含まれる場合があります。内容の正確性・完全性・最新性について、運営者はいかなる保証も行いません。
				</li>
				<li>
					<strong>データの基準時点。</strong>
					表示データは {dataDate || 'データ取得'} 時点で取得したものです。以降の更新は反映されていません。
				</li>
				<li>
					<strong>自己責任でのご利用。</strong>
					本サイトの情報を利用したこと、または利用できなかったことによって生じたいかなる損害・不利益についても、運営者は一切の責任を負いません。馬券の購入・繁殖・売買その他の判断は、必ず公式の情報源をご確認のうえ、ご自身の責任で行ってください。
				</li>
			</ul>
			<p class="agree-note">本サイトを利用された時点で、上記に同意いただいたものとみなします。</p>
			<button type="button" class="disclaimer-close" on:click={closeDisclaimer}>確認しました</button>
		</div>
	{/if}
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
	.title {
		display: flex;
		flex-direction: column;
		line-height: 1.15;
		min-width: 0;
	}
	.app-name {
		font-size: 0.7rem;
		font-weight: 600;
		color: #9aa0a6;
		white-space: nowrap;
	}
	.center-name {
		font-size: 1.05rem;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 40vw;
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
	.notice {
		position: fixed;
		top: calc(3.6rem + env(safe-area-inset-top));
		left: 50%;
		transform: translateX(-50%);
		z-index: 16;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		max-width: 92vw;
		background: rgba(30, 30, 34, 0.94);
		color: #eee;
		border: 1px solid #4a4a4a;
		border-radius: 10px;
		padding: 0.5rem 0.8rem;
		font-size: 0.82rem;
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
	}
	.notice span {
		line-height: 1.3;
	}
	.notice button {
		flex-shrink: 0;
		background: #ffd54f;
		color: #1a1a1a;
		border: none;
		border-radius: 6px;
		padding: 0.4rem 0.7rem;
		font-size: 0.82rem;
		font-weight: 600;
		cursor: pointer;
	}
	.notice button:disabled {
		background: #555;
		color: #aaa;
		cursor: default;
	}
	.data-footer {
		position: fixed;
		left: 0;
		right: 0;
		bottom: calc(0.4rem + env(safe-area-inset-bottom));
		z-index: 5;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.35rem;
		text-align: center;
		color: #6b6b6b;
		font-size: 0.7rem;
		padding: 0 0.5rem;
	}
	.footer-line {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	/* 初回ガイド: 少し目立たせる (未確認時のみ表示) */
	.disclaimer-guide {
		background: rgba(70, 55, 20, 0.9);
		color: #f0d98c;
		border: 1px solid rgba(240, 217, 140, 0.4);
		border-radius: 999px;
		padding: 0.4rem 0.9rem;
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
	}
	/* 常時出す免責リンク (確認済みでもいつでも開ける) */
	.disclaimer-link {
		background: none;
		border: none;
		color: #8a8a8a;
		font-size: 0.7rem;
		text-decoration: underline;
		cursor: pointer;
		padding: 0;
	}

	/* 免責ダイアログ */
	.disclaimer-backdrop {
		position: fixed;
		inset: 0;
		z-index: 40;
		background: rgba(0, 0, 0, 0.6);
	}
	.disclaimer-modal {
		position: fixed;
		z-index: 41;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		width: min(92vw, 440px);
		max-height: 82vh;
		overflow-y: auto;
		background: #1b1b1f;
		color: #e8e8e8;
		border: 1px solid #3a3a40;
		border-radius: 14px;
		padding: 1.2rem 1.2rem 1.3rem;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
	}
	.disclaimer-modal h2 {
		margin: 0 0 0.8rem;
		font-size: 1.05rem;
		color: #f0d98c;
	}
	.disclaimer-modal p {
		margin: 0.5rem 0;
		font-size: 0.85rem;
		line-height: 1.6;
	}
	.disclaimer-modal ul {
		margin: 0.6rem 0;
		padding-left: 1.1rem;
	}
	.disclaimer-modal li {
		margin: 0.55rem 0;
		font-size: 0.85rem;
		line-height: 1.6;
	}
	.disclaimer-modal strong {
		color: #fff;
	}
	.disclaimer-modal .agree-note {
		color: #9a9a9a;
		font-size: 0.78rem;
	}
	.disclaimer-close {
		display: block;
		width: 100%;
		margin-top: 1rem;
		background: #f0d98c;
		color: #2a230c;
		border: none;
		border-radius: 999px;
		padding: 0.75rem;
		font-size: 0.95rem;
		font-weight: 700;
		cursor: pointer;
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
	/* 初回のみの操作ガイド。画面下部・中央にそっと出す。タップで閉じる。 */
	.guide {
		position: fixed;
		left: 50%;
		bottom: calc(4.2rem + env(safe-area-inset-bottom));
		transform: translateX(-50%);
		z-index: 20;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		max-width: calc(100vw - 2rem);
		background: rgba(28, 28, 32, 0.92);
		color: #e8e8e8;
		border: 1px solid #3a3a40;
		border-radius: 14px;
		padding: 0.7rem 1.1rem;
		font-size: 0.85rem;
		line-height: 1.5;
		text-align: center;
		cursor: pointer;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45);
		animation: guide-in 0.25s ease-out;
	}
	.guide-row {
		white-space: nowrap;
	}
	.guide-dismiss {
		margin-top: 0.35rem;
		font-size: 0.72rem;
		color: #8a8a8a;
	}
	@keyframes guide-in {
		from {
			opacity: 0;
			transform: translate(-50%, 8px);
		}
		to {
			opacity: 1;
			transform: translate(-50%, 0);
		}
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

	/* 子表示モードのトグル + 世代ピッカー (左下、reset と左右対称) */
	.mode-panel {
		position: fixed;
		left: calc(0.9rem + env(safe-area-inset-left));
		bottom: calc(0.9rem + env(safe-area-inset-bottom));
		z-index: 15;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		transition: bottom 0.2s ease;
	}
	.mode-panel.with-panel {
		bottom: calc(11rem + env(safe-area-inset-bottom));
	}
	.mode-toggle {
		background: rgba(30, 30, 34, 0.92);
		color: #eee;
		border: 1px solid #444;
		border-radius: 999px;
		padding: 0.6rem 0.95rem;
		font-size: 0.9rem;
		cursor: pointer;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
		white-space: nowrap;
	}
	.mode-toggle.on {
		background: #f0d98c;
		color: #2a230c;
		border-color: #f0d98c;
		font-weight: 700;
	}
	.mode-toggle:disabled {
		opacity: 0.6;
		cursor: default;
	}
	.gen-wrap {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.25rem;
	}
	.gen-picker {
		display: flex;
		gap: 0.2rem;
		background: rgba(30, 30, 34, 0.92);
		border: 1px solid #444;
		border-radius: 999px;
		padding: 0.2rem;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
	}
	.gen-note {
		font-size: 0.7rem;
		color: #b9b9b9;
		background: rgba(20, 20, 24, 0.8);
		border-radius: 6px;
		padding: 0.1rem 0.4rem;
	}
	.gen {
		background: none;
		border: none;
		color: #ccc;
		border-radius: 999px;
		padding: 0.4rem 0.6rem;
		font-size: 0.85rem;
		cursor: pointer;
	}
	.gen.sel {
		background: #f0d98c;
		color: #2a230c;
		font-weight: 700;
	}
	.gen:disabled {
		opacity: 0.6;
		cursor: default;
	}
</style>
