<script lang="ts">
	import type { HorseNode } from './types';

	/** 選択中の馬。null なら非表示。 */
	export let node: HorseNode | null = null;
	/** この馬を中心にできるか (データファイルが存在するか)。 */
	export let centerable = false;
	/** データ存在確認中か。 */
	export let checking = false;
	/** すでにこの馬が中心か。 */
	export let isCenter = false;
	/** 系統名 (keito-master から解決済み)。 */
	export let keitoName = '';
	/** 「中心にする」タップ時。 */
	export let onCenter: (node: HorseNode) => void;
	/** 閉じる。 */
	export let onClose: () => void;

	$: meta = node
		? [node.sex, node.color, node.birthYear ? `${node.birthYear}年生` : '']
				.filter(Boolean)
				.join(' ・ ')
		: '';
</script>

{#if node}
	<div class="panel" role="dialog" aria-label="馬の詳細">
		<button class="close" on:click={onClose} aria-label="閉じる">×</button>
		<div class="body">
			<div class="name">{node.name || node.kana || node.eng || '(名称不明)'}</div>
			{#if node.eng && node.eng !== node.name}
				<div class="eng">{node.eng}</div>
			{/if}
			{#if meta}<div class="meta">{meta}</div>{/if}
			{#if keitoName}<div class="keito">系統: {keitoName}</div>{/if}
		</div>

		<div class="actions">
			{#if isCenter}
				<button class="center" disabled>表示中</button>
			{:else if checking}
				<button class="center" disabled>確認中…</button>
			{:else if centerable}
				<button class="center" on:click={() => node && onCenter(node)}>この馬を中心にする</button>
			{:else}
				<button class="center" disabled>血統データなし</button>
			{/if}
		</div>
	</div>
{/if}

<style>
	.panel {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 20;
		background: rgba(18, 18, 20, 0.96);
		border-top: 1px solid #333;
		padding: 1rem 1.1rem calc(1rem + env(safe-area-inset-bottom));
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		box-shadow: 0 -6px 24px rgba(0, 0, 0, 0.5);
	}
	.close {
		position: absolute;
		top: 0.4rem;
		right: 0.5rem;
		background: none;
		border: none;
		color: #aaa;
		font-size: 1.6rem;
		line-height: 1;
		padding: 0.2rem 0.5rem;
		cursor: pointer;
	}
	.name {
		font-size: 1.25rem;
		font-weight: 700;
	}
	.eng {
		color: #9aa0a6;
		font-size: 0.9rem;
	}
	.meta {
		margin-top: 0.35rem;
		color: #d0d0d0;
		font-size: 0.95rem;
	}
	.keito {
		margin-top: 0.15rem;
		color: #d0d0d0;
		font-size: 0.9rem;
	}
	.actions {
		display: flex;
	}
	.center {
		flex: 1;
		padding: 0.85rem 1rem;
		font-size: 1.05rem;
		font-weight: 600;
		border: none;
		border-radius: 10px;
		background: #ffd54f;
		color: #1a1a1a;
		cursor: pointer;
	}
	.center:disabled {
		background: #3a3a3d;
		color: #888;
		cursor: default;
	}
</style>
