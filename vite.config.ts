import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// Svelte and Kit options live in svelte.config.js; passing any of them here
// would make that file be ignored. Only build-tool concerns belong in this one.
export default defineConfig({
	plugins: [sveltekit()],
	server: { proxy: { '/api': 'http://localhost:8000' } }
});
