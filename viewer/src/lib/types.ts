// pipeline が生成する配信 JSON のデータ契約 (docs/design.md §3 に対応)。

/** 馬ノード (horses/{id}.json / full/{id}.json の nodes 要素)。 */
export interface HorseNode {
	/** 一意キー ("H" + 繁殖登録番号)。ファイル名・中心切替に使う。 */
	id: string;
	/** 血統登録番号 (競走馬のみ。輸入種牡馬等は空)。検索/表示の補助。 */
	kettoNum: string;
	name: string;
	kana: string;
	eng: string;
	/** デコード済み性別ラベル (牡/牝/セン)。 */
	sex: string;
	/** デコード済み毛色ラベル。 */
	color: string;
	birthYear: number | null;
	/** 系統ID (色分けキー)。未知は "other"。 */
	keitoId: string;
	/** 中心=0, 祖先=+n, 子孫=-n。 */
	generation: number;
}

/** 親子エッジ。 */
export interface PedigreeEdge {
	/** 親ノード id。 */
	source: string;
	/** 子ノード id。 */
	target: string;
	/** 父方 / 母方。 */
	parent: 'father' | 'mother';
}

/** 馬ノードファイル / API レスポンスの中身。 */
export interface HorseGraph {
	center: string;
	nodes: HorseNode[];
	edges: PedigreeEdge[];
	/** 子孫の間引き情報 (任意)。 */
	meta?: {
		/** 直仔が多く「代表的な子」に絞られているか。 */
		truncatedChildren: boolean;
		/** 中心馬の直仔の総数。 */
		totalChildren: number;
	};
}

/** 検索インデックス (search-index.json) の要素。 */
export interface SearchEntry {
	/** ノード id ("H" + 繁殖登録番号)。中心指定に使う。 */
	id: string;
	name: string;
	kana: string;
	eng: string;
}

/** 系統マスタ (keito-master.json)。keitoId -> {name, color}。"other" を含む。 */
export type KeitoMaster = Record<string, { name: string; color: string }>;
