import type { PaperDetail, PaperListItem, ReconstructOpts, Review } from './types';

export class ApiError extends Error {
	violations?: string[];
	constructor(detail: string, violations?: string[]) {
		super(detail);
		this.violations = violations;
	}
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(path, init);
	const data = await res.json().catch(() => ({}));
	if (!res.ok) throw new ApiError(data.detail ?? `${res.status} on ${path}`, data.violations);
	return data as T;
}

// Export commits and tags, so it is a POST — which means the file arrives as a
// response body rather than through a plain link, and is saved from a blob.
async function postDownload(path: string, filename: string): Promise<void> {
	const res = await fetch(path, { method: 'POST' });
	if (!res.ok) {
		const data = await res.json().catch(() => ({}));
		throw new ApiError(data.detail ?? `${res.status} on ${path}`, data.violations);
	}
	const url = URL.createObjectURL(await res.blob());
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	link.click();
	URL.revokeObjectURL(url);
}

const post = (path: string, body?: unknown) =>
	api<Record<string, unknown>>(path, {
		method: 'POST',
		headers: body ? { 'content-type': 'application/json' } : undefined,
		body: body ? JSON.stringify(body) : undefined
	});

export const listPapers = () => api<PaperListItem[]>('/api/papers');
export const getPaper = (id: string) => api<PaperDetail>(`/api/papers/${id}`);
export const uploadPaper = (form: FormData) =>
	api<{ id: string }>('/api/papers', { method: 'POST', body: form });
export const getReview = (id: string, n: number) => api<Review>(`/api/papers/${id}/reviews/${n}`);
export const startReview = (id: string) => post(`/api/papers/${id}/review`);
export const doEdit = (id: string, command: string) => post(`/api/papers/${id}/do`, { command });
export const approveProposal = (id: string) => post(`/api/papers/${id}/approve`);
export const rejectProposal = (id: string) => post(`/api/papers/${id}/reject`);
export const acceptPaper = (id: string) => post(`/api/papers/${id}/accept`);
export const rerunPaper = (id: string, opts?: ReconstructOpts) =>
	post(`/api/papers/${id}/rerun`, opts);
export const refinePaper = (id: string, opts: ReconstructOpts & { instruction?: string }) =>
	post(`/api/papers/${id}/refine`, opts);
export const exportPaper = (id: string) => postDownload(`/api/papers/${id}/export`, `${id}.pdf`);
