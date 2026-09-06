// 3d-force-graph のラッパ。HorseGraph を 3D フォースダイレクテッドグラフとして描画する。
//
// スマホ中心の設計 (docs/design.md §4):
//  - ノード色: 系統 (keitoId) を keito-master の色で。中心馬・選択馬は強調。
//  - リンク: 父方=青細線 / 母方=赤太線+粒子 (3D では破線が扱えないため)。
//  - インブリード強調: 複数の子から参照される同一ノードを強調 (太く/発光)。
//  - ラベル: ホバーではなく、中心から 5 世代までのノードに **常時ラベル** を描画
//    (スマホにはホバーが無いため)。
//  - ノードタップ = 「選択」。中心切り替えは行わず onSelect を呼ぶ (詳細パネル表示用)。
//    実際の中心切り替えは詳細パネルのボタン経由で行う。

import type { HorseGraph, HorseNode, KeitoMaster, PedigreeEdge } from './types';

const CENTER_COLOR = '#ffffff';
const OTHER_COLOR = '#999999';
const SELECT_COLOR = '#ffd54f';
// 常時ラベルを出す世代のしきい値 (中心から |generation| <= この値)。
const LABEL_MAX_GEN = 5;
// ラベルの不透明度は「世代ベース」と「距離ベース」の大きい方を採用する (max)。
//  - 世代ベース: 中心に近い世代ほど濃い。普段の見やすさの基本。
//  - 距離ベース: スワイプで回り込んで手前に来たノードは濃くなる。奥の馬を読むため。
// max にすることで「世代的に薄い奥の馬も、手前に回せば濃くなる」を実現する。

// 世代 (|generation|) → 基本不透明度。中心=0 と 1 世代は最大。
const GEN_OPACITY: Record<number, number> = { 0: 1, 1: 1, 2: 0.7, 3: 0.45, 4: 0.28, 5: 0.15 };
const GEN_OPACITY_MIN = 0.15;

// 距離ベースは「絶対距離」ではなく、そのフレームで見えているラベルの
// 最小〜最大距離で**相対正規化**する。これによりズーム/回り込みの度合いに
// 関係なく「今いちばん手前のノードは必ず濃い」が保証される。
const DIST_OPACITY_MIN = 0.1; // 相対的に一番奥のラベルの下限

function genOpacity(generation: number): number {
	return GEN_OPACITY[Math.abs(generation)] ?? GEN_OPACITY_MIN;
}

export interface GraphHandle {
	/** グラフデータを差し替える (中心切り替え時)。 */
	update(graph: HorseGraph): void;
	/** 選択ノードを設定 (ハイライト用)。null で解除。 */
	setSelected(id: string | null): void;
	/** カメラを既定アングル (正面やや上・原点注視) に戻す。 */
	resetView(): void;
	/** リサイズ。 */
	resize(width: number, height: number): void;
	/** 破棄。 */
	destroy(): void;
}

export interface RenderOptions {
	keito: KeitoMaster;
	/** ノードタップ時に呼ばれる。選択された馬を渡す (中心切り替えはしない)。 */
	onSelect: (node: HorseNode) => void;
	/** 大規模グラフ (全部盛り) 用に描画を簡略化 (LOD)。 */
	lod?: boolean;
}

/** 各ノードについて「子側から参照される数」を数え、クロス(インブリード)を検出する。 */
export function computeInbreeding(edges: PedigreeEdge[]): Set<string> {
	const parentRefCount = new Map<string, number>();
	for (const e of edges) {
		parentRefCount.set(e.source, (parentRefCount.get(e.source) ?? 0) + 1);
	}
	const crossed = new Set<string>();
	for (const [id, count] of parentRefCount) {
		if (count >= 2) crossed.add(id);
	}
	return crossed;
}

function nodeColor(node: HorseNode, keito: KeitoMaster, selectedId: string | null): string {
	if (node.id === selectedId) return SELECT_COLOR;
	if (node.generation === 0) return CENTER_COLOR;
	return keito[node.keitoId]?.color ?? keito.other?.color ?? OTHER_COLOR;
}

export async function createGraph(
	container: HTMLElement,
	initial: HorseGraph,
	opts: RenderOptions
): Promise<GraphHandle> {
	const { default: ForceGraph3D } = await import('3d-force-graph');
	const THREE = await import('three');

	let crossed = computeInbreeding(initial.edges);
	let selectedId: string | null = null;

	// 生成したラベルスプライトを追跡し、フェードを毎フレーム適用する。
	type LabelInfo = {
		sprite: InstanceType<typeof THREE.Sprite>;
		nodeId: string;
		important: boolean;
		isCenter: boolean;
		generation: number;
	};
	let labels: LabelInfo[] = [];

	// レイアウト: Y 座標を世代で固定して「祖先=上 / 子孫=下」に分ける。
	//  - 中心 (generation=0) は原点。
	//  - 祖先 (generation>0) は上 (+Y)、子孫 (generation<0) は下 (-Y)。
	//  - X/Z はフォースで自由に広がる (横方向の有機的レイアウト)。
	// fy を与えると Y は固定され、fx/fz は未指定なのでシミュレーションで動く。
	const GEN_Y_GAP = 60; // 1 世代あたりの縦間隔
	// 同世代を完全に同一平面 (Y 固定) に置くと、平面内に押し込められて均一な円盤状の
	// 塊になる。Y にランダムなゆらぎを足して平面をほぐす (世代分けは大まかに維持)。
	// ゆらぎは世代間隔より十分小さくして、祖先=上/子孫=下 の分離は保つ。
	const Y_JITTER = 55;
	const toGraphData = (g: HorseGraph) => ({
		nodes: g.nodes.map((n) => {
			if (n.generation === 0) return { ...n, fx: 0, fy: 0, fz: 0 };
			const jitter = (Math.random() * 2 - 1) * Y_JITTER; // -Y_JITTER..+Y_JITTER
			const fy = n.generation * GEN_Y_GAP + jitter; // 祖先=上, 子孫=下 + ゆらぎ
			return { ...n, fy };
		}),
		links: g.edges.map((e) => ({ ...e }))
	});

	const isFather = (l: PedigreeEdge) => l.parent === 'father';

	// 馬名テキストを 3D スプライトとして生成 (常時ラベル用)。
	// style: 'center'=中心馬(大きく黄背景・黒太字・枠), 'selected'=選択馬(オレンジ枠),
	//        'normal'=通常(暗背景・白字)。
	type LabelStyle = 'normal' | 'selected' | 'center';
	const roundRect = (
		ctx: CanvasRenderingContext2D,
		x: number,
		y: number,
		w: number,
		h: number,
		r: number
	) => {
		ctx.beginPath();
		ctx.moveTo(x + r, y);
		ctx.arcTo(x + w, y, x + w, y + h, r);
		ctx.arcTo(x + w, y + h, x, y + h, r);
		ctx.arcTo(x, y + h, x, y, r);
		ctx.arcTo(x, y, x + w, y, r);
		ctx.closePath();
		ctx.fill();
	};

	const makeLabelSprite = (text: string, style: LabelStyle) => {
		const canvas = document.createElement('canvas');
		const ctx = canvas.getContext('2d')!;
		// 中心馬は少しだけ大きく (1.3倍程度)。派手にしすぎない。
		const fontSize = style === 'center' ? 62 : 48;
		const font = `bold ${fontSize}px sans-serif`;
		ctx.font = font;
		const padding = style === 'center' ? 16 : 12;
		const w = Math.ceil(ctx.measureText(text).width) + padding * 2;
		const h = fontSize + padding * 2;
		canvas.width = w;
		canvas.height = h;

		// 背景 (角丸で上品に)。中心=淡い黄、選択=やや明るい暗色、通常=暗い半透明。
		if (style === 'center') ctx.fillStyle = 'rgba(245,224,140,0.95)'; // 淡い黄
		else if (style === 'selected') ctx.fillStyle = 'rgba(40,40,44,0.92)';
		else ctx.fillStyle = 'rgba(0,0,0,0.55)';
		roundRect(ctx, 0, 0, w, h, Math.min(h / 2, 16));

		// 文字
		ctx.font = font;
		ctx.fillStyle = style === 'center' ? '#1a1a1a' : '#ffffff';
		ctx.textBaseline = 'middle';
		ctx.fillText(text, padding, h / 2);

		const texture = new THREE.CanvasTexture(canvas);
		texture.minFilter = THREE.LinearFilter;
		const material = new THREE.SpriteMaterial({ map: texture, depthWrite: false, transparent: true });
		const sprite = new THREE.Sprite(material);
		const scale = 0.14;
		sprite.scale.set(w * scale, h * scale, 1);
		return sprite;
	};

	// ラベル対象外のノードには空の Group を返す (nodeThreeObjectExtend=true なので
	// 既定の球は残る)。undefined を返さず常に Object3D を返して型を合わせる。
	const emptyObject = () => new THREE.Group();
	const labelObject = (n: HorseNode): InstanceType<typeof THREE.Object3D> => {
		if (Math.abs(n.generation) > LABEL_MAX_GEN) return emptyObject();
		const name = n.name || n.kana || n.eng || n.id;
		const isCenter = n.generation === 0;
		const important = isCenter || n.id === selectedId;
		const style: LabelStyle = isCenter ? 'center' : n.id === selectedId ? 'selected' : 'normal';
		const sprite = makeLabelSprite(name, style);
		labels.push({ sprite, nodeId: n.id, important, isCenter, generation: n.generation });
		return sprite;
	};

	const graph = new ForceGraph3D(container)
		.graphData(toGraphData(initial))
		.nodeId('id')
		.nodeColor((n) => nodeColor(n as unknown as HorseNode, opts.keito, selectedId))
		.nodeVal((n) => {
			const h = n as unknown as HorseNode;
			return h.generation === 0 ? 6 : crossed.has(h.id) ? 4 : 2;
		})
		// 常時ラベル (中心から5世代まで)。ノード本体も残す。
		.nodeThreeObjectExtend(true)
		.nodeThreeObject((n) => labelObject(n as unknown as HorseNode))
		.linkDirectionalArrowLength(3)
		.linkColor((l) => (isFather(l as unknown as PedigreeEdge) ? '#8ab4f8' : '#f28b82'))
		.linkWidth((l) => (isFather(l as unknown as PedigreeEdge) ? 0.5 : 1.2))
		.linkDirectionalParticles((l) => (isFather(l as unknown as PedigreeEdge) ? 0 : 2))
		.linkDirectionalParticleWidth(1.5)
		// 表示前に裏で配置を進めておく (warmup)。表示時点で概ね落ち着いており、
		// 「表示直後にノードがぶつかってプルプル動く」不快感を抑える。
		.warmupTicks(120)
		// 総ティック数を抑えて早めに静止させる (いつまでも微振動しない)。
		.cooldownTicks(80)
		// タップ = 選択 (中心切り替えはしない)。
		.onNodeClick((n) => opts.onSelect(n as unknown as HorseNode));

	// 反発力を強める: ノード同士がより離れ、密集した「だんご」をほぐす。
	const chargeForce = graph.d3Force('charge') as
		| { strength(s: number): unknown; distanceMax(d: number): unknown }
		| undefined;
	chargeForce?.strength(-80); // 既定(-30程度)より強い反発
	chargeForce?.distanceMax(400); // 反発の及ぶ距離に上限 (遠すぎる相互作用を切って安定させる)

	if (opts.lod) {
		// 大規模グラフ: ラベルを空 Group にして描画を軽くする。
		graph.nodeThreeObject(() => new THREE.Group()).nodeResolution(4).cooldownTicks(60);
	}

	const refresh = () => {
		// 色/ラベルの再評価を促す (同じアクセサを再設定すると再描画される)。
		// ラベルは作り直されるので追跡リストをクリアしてから再構築させる。
		labels = [];
		graph.nodeColor(graph.nodeColor());
		graph.nodeThreeObject(graph.nodeThreeObject());
	};

	// アングルを正面 (やや上) に戻す。ズーム感を出さないため、
	// 現在のカメラ〜原点の距離を保ったまま向きだけ変える。
	// 既定の見下ろし角度 (仰角) を保つよう、方向ベクトルを正規化して現在距離を掛ける。
	const DEFAULT_DIR = (() => {
		const v = new THREE.Vector3(0, 120, 620); // 正面やや上の方向
		v.normalize();
		return v;
	})();
	const resetView = (ms = 600) => {
		const cam = graph.camera();
		// 現在のカメラ〜原点の距離を維持 (ズームを変えない)。
		const dist = Math.hypot(cam.position.x, cam.position.y, cam.position.z) || 620;
		const pos = {
			x: DEFAULT_DIR.x * dist,
			y: DEFAULT_DIR.y * dist,
			z: DEFAULT_DIR.z * dist
		};
		// カメラの up ベクトル (ロール/傾き) を真上に戻す。
		// スワイプ操作 (Trackball) で up が傾くため、これを戻さないと
		// 正面に戻しても画面が斜めのままになる。
		cam.up.set(0, 1, 0);
		const controls = graph.controls() as { target?: { set(x: number, y: number, z: number): void }; update?: () => void };
		controls?.target?.set(0, 0, 0);
		controls?.update?.();
		graph.cameraPosition(pos, { x: 0, y: 0, z: 0 }, ms);
	};
	// 新しいグラフを読み込んだら「最初の描画時に一度だけ」ズームを内容に合わせる。
	//  - warmupTicks(120) で表示前に配置がほぼ決まっているため、初回ティックで即フィット
	//    すれば表示時点で適切なズームになる。
	//  - onEngineStop(数秒後の安定時)ではなく初回ティックで行うことで、「表示後に
	//    時間差でヌルッとズームが動く」不快感をなくす。以降は一切自動調整せず、
	//    ズームはユーザーに委ねる。
	//  - グラフごとにフィットするので、大→小のズーム持ち越し問題も起きない。
	let needsFit = true;
	graph.onEngineTick(() => {
		if (needsFit) {
			graph.zoomToFit(0, 60); // アニメーション0=瞬時にフィット (時間差の動きなし)
			needsFit = false;
		}
	});

	// フェード: 毎フレーム、世代ベースと「相対距離ベース」の max を適用する。
	// 相対距離ベース = そのフレームの全ラベル距離の min..max で正規化するので、
	// ズームや回り込みに関係なく「今いちばん手前のラベルは必ず濃い」。
	const camPos = new THREE.Vector3();
	const spritePos = new THREE.Vector3();
	let distBuf = new Float64Array(0);
	let rafId = 0;
	const fadeLoop = () => {
		const cam = graph.camera();
		if (cam && labels.length) {
			cam.getWorldPosition(camPos);

			// 1st pass: 非 important ラベルのカメラ距離を集め、min/max を求める。
			if (distBuf.length < labels.length) distBuf = new Float64Array(labels.length);
			let dmin = Infinity;
			let dmax = -Infinity;
			for (let i = 0; i < labels.length; i++) {
				const { sprite, important } = labels[i];
				if (important) {
					distBuf[i] = -1;
					continue;
				}
				sprite.getWorldPosition(spritePos);
				const d = camPos.distanceTo(spritePos);
				distBuf[i] = d;
				if (d < dmin) dmin = d;
				if (d > dmax) dmax = d;
			}
			const span = dmax - dmin;

			// 中心馬ラベルの明滅係数 (0.25..1.0 を速めに往復。くっきり点滅)。
			const blink = 0.625 + 0.375 * Math.sin(performance.now() / 170);

			// 2nd pass: opacity を適用。
			for (let i = 0; i < labels.length; i++) {
				const { sprite, important, isCenter, generation } = labels[i];
				const mat = sprite.material as InstanceType<typeof THREE.SpriteMaterial>;
				if (isCenter) {
					mat.opacity = blink; // 中心馬は明滅させて目立たせる
					continue;
				}
				if (important) {
					mat.opacity = 1;
					continue;
				}
				// 相対距離: 手前(dmin)=1、奥(dmax)=DIST_OPACITY_MIN。
				let relDist = 1;
				if (span > 1e-6) {
					const t = (distBuf[i] - dmin) / span; // 0(手前)..1(奥)
					relDist = 1 - t * (1 - DIST_OPACITY_MIN);
				}
				mat.opacity = Math.max(genOpacity(generation), relDist);
			}
		}
		rafId = requestAnimationFrame(fadeLoop);
	};
	rafId = requestAnimationFrame(fadeLoop);

	return {
		update(g: HorseGraph) {
			crossed = computeInbreeding(g.edges);
			selectedId = null;
			labels = [];
			needsFit = true; // 新グラフに合わせてズームし直す
			graph.graphData(toGraphData(g));
		},
		setSelected(id: string | null) {
			selectedId = id;
			refresh();
		},
		resetView() {
			resetView(600);
		},
		resize(width: number, height: number) {
			graph.width(width).height(height);
		},
		destroy() {
			cancelAnimationFrame(rafId);
			labels = [];
			graph._destructor?.();
			container.replaceChildren();
		}
	};
}
