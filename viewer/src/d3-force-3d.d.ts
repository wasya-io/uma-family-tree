// d3-force-3d は型定義を同梱していない (JS のみ)。使用する forceX/forceZ のみ最小宣言する。
// 3d-force-graph が内部で使う d3-force-3d を、レイアウトの X/Z 中心寄せ (横広がり抑制) に流用している。
declare module 'd3-force-3d' {
	interface PositionForce {
		strength(s: number): PositionForce;
		(alpha: number): void;
	}
	export function forceX(x?: number): PositionForce;
	export function forceY(y?: number): PositionForce;
	export function forceZ(z?: number): PositionForce;
}
