import adapter from '@sveltejs/adapter-static';

// All Svelte/Kit options live here — passing any of them inline to sveltekit()
// in vite.config.ts makes this file be ignored wholesale.
export default {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// The app is fully client-side (every view renders off /api fetches), so it
		// builds to a static SPA that `papercli serve --static` can host.
		adapter: adapter({ fallback: 'index.html' })
	}
};
