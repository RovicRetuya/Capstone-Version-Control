import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// The DeFaketive Flask app (server.py, on port 5000 while developing; on the live site serve.py serves both) does all the
// real work: accounts, scans, the review checker and the wording of every verdict.
// This app is only a new face for it, so every /api call is passed straight through.
declare const process: { env: Record<string, string | undefined> };
const flask = process.env.DEFAKETIVE_API ?? 'http://127.0.0.1:5000';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// One page that loads the app in the browser; every address falls back to it.
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		proxy: { '/api': flask }
	},
	preview: {
		proxy: { '/api': flask }
	}
});
