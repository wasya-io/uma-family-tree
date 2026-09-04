// 3d-force-graph のラッパ。HorseGraph を 3D フォースダイレクテッドグラフとして描画する。
//
// 表示方針 (docs/design.md §4):
//  - ノード色: 系統 (keitoId) を keito-master の色で。中心馬は強調。
//  - リンク: 父方=実線 / 母方=破線。
//  - インブリード強調: 複数の子から集まる同一ノード (入次数>=2 相当) を強調。
//  - ノードクリックで中心切り替え (onCenterChange コールバック)。

import type { HorseGraph, HorseNode, KeitoMaster, PedigreeEdge } from './types';

const CENTER_COLOR = '#ffffff';
const OTHER_COLOR = '#999999';

export interface GraphHandle {
	/** グラフデータを差し替える (中心切り替え時)。 */
	update(graph: HorseGraph): void;
	/** リサイズ。 */
	resize(width: number, height: number): void;
	/** 破棄。 */
	destroy(): void;
}

export interface RenderOptions {
	keito: KeitoMaster;
	/** ノードクリック時に呼ばれる。新しい中心 KettoNum を渡す。 */
	onCenterChange: (kettoNum: string) => void;
	/** 大規模グラフ (全部盛り) 用に描画を簡略化 (LOD)。 */
	lod?: boolean;
}

/** 各ノードについて「子側から参照される数」を数え、クロス(インブリード)を検出する。 */
export function computeInbreeding(edges: PedigreeEdge[]): Set<string> {
	const parentRefCount = new Map<string, number>();
	for (const e of edges) {
		// e.source が親。親が複数の子(target)から参照される = クロス。
		parentRefCount.set(e.source, (parentRefCount.get(e.source) ?? 0) + 1);
	}
	const crossed = new Set<string>();
	for (const [id, count] of parentRefCount) {
		if (count >= 2) crossed.add(id);
	}
	return crossed;
}

function nodeColor(node: HorseNode, keito: KeitoMaster): string {
	if (node.generation === 0) return CENTER_COLOR;
	return keito[node.keitoId]?.color ?? keito.other?.color ?? OTHER_COLOR;
}

/**
 * 3d-force-graph を初期化してコンテナにマウントする。
 *
 * 3d-force-graph は実行時に動的 import する (SSR 回避 & Three.js を含む重いバンドルの遅延ロード)。
 */
export async function createGraph(
	container: HTMLElement,
	initial: HorseGraph,
	opts: RenderOptions
): Promise<GraphHandle> {
	const { default: ForceGraph3D } = await import('3d-force-graph');

	let crossed = computeInbreeding(initial.edges);

	const toGraphData = (g: HorseGraph) => ({
		nodes: g.nodes.map((n) => ({ ...n })),
		links: g.edges.map((e) => ({ ...e }))
	});

	const isFather = (l: PedigreeEdge) => l.parent === 'father';

	const graph = new ForceGraph3D(container)
		.graphData(toGraphData(initial))
		.nodeId('id')
		.nodeLabel((n) => labelHtml(n as unknown as HorseNode))
		.nodeColor((n) => nodeColor(n as unknown as HorseNode, opts.keito))
		.nodeVal((n) => {
			const h = n as unknown as HorseNode;
			return h.generation === 0 ? 6 : crossed.has(h.id) ? 4 : 2;
		})
		.linkDirectionalArrowLength(3)
		// 父方=青 / 母方=赤 で区別 (3D では破線が扱えないため色で表現)。
		.linkColor((l) => (isFather(l as unknown as PedigreeEdge) ? '#8ab4f8' : '#f28b82'))
		// 母方リンクは太めにして視認性を上げる。
		.linkWidth((l) => (isFather(l as unknown as PedigreeEdge) ? 0.5 : 1.2))
		// 母方リンクには流れる粒子を付け、父方(実線相当)と質感で区別する。
		.linkDirectionalParticles((l) => (isFather(l as unknown as PedigreeEdge) ? 0 : 2))
		.linkDirectionalParticleWidth(1.5)
		.onNodeClick((n) => opts.onCenterChange((n as unknown as HorseNode).id));

	if (opts.lod) {
		// 大規模グラフ: ラベル省略・簡略描画。
		graph.nodeLabel('').nodeResolution(4).cooldownTicks(60);
	}

	return {
		update(g: HorseGraph) {
			crossed = computeInbreeding(g.edges);
			graph.graphData(toGraphData(g));
		},
		resize(width: number, height: number) {
			graph.width(width).height(height);
		},
		destroy() {
			graph._destructor?.();
			container.replaceChildren();
		}
	};
}

function labelHtml(n: HorseNode): string {
	const parts = [n.name || n.kana || n.id];
	const meta = [n.sex, n.color, n.birthYear ? `${n.birthYear}年` : ''].filter(Boolean).join(' / ');
	if (meta) parts.push(meta);
	return parts.join('\n');
}
