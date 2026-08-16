export type Section = { level: number; title: string };
export type Reference = { key: string; text: string };

export type ParsedPaper = {
	title: string | null;
	abstract: string | null;
	sections: Section[];
	citations: Record<string, number>;
	references: Reference[];
	unresolved: string[];
	uncited: string[];
};

export type RepoState = {
	accepted: boolean;
	from_pdf: boolean;
	parse_rounds: number;
	reviews: number[];
	exports: number;
	proposal: string | null;
	busy: boolean;
};

export type Run = {
	kind: string;
	status: 'running' | 'done' | 'error';
	progress: string[];
	error: string | null;
	elapsed: number;
};

export type ReconstructOpts = { model?: string; effort?: string };

/** Where a source-native id resolves; the API owns the URL shape, not the client. */
export type SourceLink = { api: string; id: string; url: string | null };

export type RefSummary = {
	key: string;
	status: string;
	title: string;
	author: string;
	year: number | null;
	ids: SourceLink[];
	url: string | null;
	notes: string[];
};

export type Divergence = {
	kind: 'missing' | 'added' | 'changed';
	original: string;
	rebuilt: string;
	page: number | null;
};

export type Parity = {
	paritex_version?: string;
	parity: { ratio: number; divergences: Divergence[] };
	pages_original: number;
	pages_rebuilt: number;
};

export type Proposal = { branch: string; command: string; diff: string };

export type PaperDetail = {
	id: string;
	title: string;
	state: RepoState;
	run: Run | null;
	parse: ParsedPaper | null;
	refs: RefSummary[];
	parity: Parity | null;
	proposal: Proposal | null;
	log: string[];
};

export type PaperListItem = { id: string; title: string; accepted: boolean };

export type FindingSource = {
	api: string;
	id: string;
	key: string | null;
	title: string | null;
	url: string | null;
};

export type Finding = {
	kind: string;
	severity: 'minor' | 'major';
	confidence: number;
	section: string | null;
	claim: string | null;
	cites: string[];
	sources: FindingSource[];
	verdict: string | null;
	note: string;
	suggestion: string | null;
};

export type Review = { n: number; paper: string; findings: Finding[] };
