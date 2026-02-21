import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte({ compilerOptions: { customElement: true } })],
  build: {
    lib: {
      entry: 'src/index.js',
      formats: ['es'],
      fileName: 'plugin',
    },
    outDir: '../dist',
    emptyOutDir: true,
  },
});
