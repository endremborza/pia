import { expect, test } from '@playwright/test';

const TEX_FIXTURE = 'e2e/fixtures/rankless-incomplete.tex';
const PDF_FIXTURE = 'e2e/fixtures/rankless.pdf';

test('full loop: resolve, review, edit, approve, export', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByRole('button', { name: 'Upload' })).toBeEnabled();
	await page.getByLabel('LaTeX (.tex)').check();
	await page.locator('input[type=file]').setInputFiles(TEX_FIXTURE);
	await page.getByRole('button', { name: 'Upload' }).click();
	await expect(page).toHaveURL(/\/papers\//);

	// resolution against live APIs finishes and the store view appears
	await expect(page.getByText('verified online')).toBeVisible({ timeout: 120_000 });
	await expect(page.getByText('parse/1')).toBeVisible();

	// peer review with the (configured) agent backend
	await page.getByRole('button', { name: 'Request peer review' }).click();
	await expect(page.getByText(/Review 1 — 1 finding/)).toBeVisible({ timeout: 120_000 });
	await expect(page.getByText('Leiden Manifesto', { exact: false }).first()).toBeVisible();
	await expect(page.getByText('missing-citation')).toBeVisible();

	// natural-language edit lands as a proposal diff
	await page.getByLabel('edit instruction').fill('make the conclusion punchier');
	await page.getByRole('button', { name: 'Run edit' }).click();
	await expect(page.getByText(/^Proposal:/)).toBeVisible({ timeout: 120_000 });
	await expect(page.locator('.diff')).toContainText('Improved for clarity via papercli.');

	// approve = fast-forward merge; the history shows the commit
	await page.getByRole('button', { name: /Approve — merge to main/ }).click();
	await expect(page.getByLabel('edit instruction')).toBeVisible({ timeout: 30_000 });
	await expect(page.locator('.log')).toContainText('papercli do: make the conclusion punchier');

	// export builds a real PDF (POST: it commits the refreshed files and tags export/N)
	const id = page.url().split('/papers/')[1];
	const res = await page.request.post(`/api/papers/${id}/export`);
	expect(res.ok()).toBeTruthy();
	expect(res.headers()['content-type']).toContain('application/pdf');
	expect((await res.body()).subarray(0, 4).toString()).toBe('%PDF');
});

// The other door: a PDF is reconstructed and then stops, because nothing
// downstream may run on a guess the user has not ruled on.
test('pdf upload reconstructs and waits for acceptance', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByRole('button', { name: 'Upload' })).toBeEnabled();
	await page.getByLabel('PDF').check();
	await page.locator('input[type=file]').setInputFiles(PDF_FIXTURE);
	await page.getByRole('button', { name: 'Upload' }).click();

	await expect(page).toHaveURL(/\/papers\/rankless-/);
	await expect(page.getByRole('heading', { name: 'Is this your paper?' })).toBeVisible({
		timeout: 90_000
	});
	await expect(page.getByText('Word-level parity')).toBeVisible();
	await expect(page.getByText(/in-text citation keys extracted/)).toBeVisible();

	// all three verdicts are offered, and none of them is "edit it yourself"
	await expect(page.getByRole('button', { name: /Accept — this is my paper/ })).toBeVisible();
	await expect(page.getByRole('button', { name: /Re-run from scratch/ })).toBeVisible();
	await expect(page.getByRole('button', { name: /Refine this candidate/ })).toBeVisible();
	await expect(page.getByLabel('edit instruction')).toHaveCount(0);
});
