import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      fallback: 'index.html' // Essential for SPA routing
    }),
    paths: {
      // This tells SvelteKit to serve assets from /Chapar/ instead of /
      base: process.argv.includes('dev') ? '' : '/Chapar'
    }
  }
};

export default config;
