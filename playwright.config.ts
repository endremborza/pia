import { defineConfig, devices } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';

function dotenv(path = '.env'): Record<string, string> {
	if (!existsSync(path)) return {};
	return Object.fromEntries(
		readFileSync(path, 'utf8')
			.split('\n')
			.map((line) => line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/))
			.filter((m): m is RegExpMatchArray => m !== null)
			.map((m) => [m[1], m[2]])
	);
}

export default defineConfig({
	testDir: 'e2e',
	timeout: 120_000,
	webServer: [
		{
			command: 'uv run --extra server papercli serve --port 8000',
			port: 8000,
			reuseExistingServer: true,
			env: {
				...process.env,
				...dotenv(),
				PAPERCLI_CONFIG: 'e2e/fixtures/papercli-e2e.toml',
				PAPERCLI_AGENT_BACKEND: '',
				PAPERCLI_PASSWORD: ''
			}
		},
		{
			command: 'npm run dev',
			port: 5173,
			reuseExistingServer: true
		}
	],
	use: { baseURL: 'http://localhost:5173' },
	projects: [
		{
			name: 'e2e',
			testIgnore: '**/demo.spec.ts',
			use: { ...devices['Desktop Chrome'] }
		},
		{
			name: 'demo',
			testMatch: '**/demo.spec.ts',
			use: {
				...devices['Desktop Chrome'],
				viewport: { width: 1280, height: 900 },
				launchOptions: { slowMo: 400 }
			}
		}
	]
});
