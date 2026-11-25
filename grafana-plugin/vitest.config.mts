import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

import pluginJson from './src/plugin.json' with { type: 'json' };

const src = fileURLToPath(new URL('./src/', import.meta.url));
const timezone = process.env.TZ === 'Europe/London' ? 'london' : 'utc';
const report = process.env.VITEST_REPORT === 'true';

export default defineConfig({
  define: {
    'process.env.PLUGIN_ID': JSON.stringify(pluginJson.id),
  },
  resolve: {
    alias: [
      { find: /^react-inlinesvg$/, replacement: `${src}test-utils/inlineSvgMock.tsx` },
      { find: /^grafana\/app\/.*$/, replacement: `${src}test-utils/grafanaMock.ts` },
      {
        find: /^(assets|components|containers|dashboards|helpers|icons|models|navbar|network|pages|plugin|shims|state|styles)\//,
        replacement: `${src}$1/`,
      },
    ],
  },
  test: {
    environment: 'jsdom',
    environmentOptions: { jsdom: { url: 'http://localhost/' } },
    globals: true,
    // Grafana publishes extensionless imports that need Vite resolution in Node.
    server: { deps: { inline: [/\/node_modules\/@grafana\//] } },
    include: ['src/**/__tests__/**/*.{js,jsx,ts,tsx}', 'src/**/*.{spec,test}.{js,jsx,ts,tsx}'],
    setupFiles: ['./vitest.setup.ts'],
    testTimeout: 10_000,
    reporters: report ? ['default', 'json'] : ['default'],
    outputFile: report ? { json: `vitest-report-${timezone}.json` } : undefined,
    silent: process.env.VITEST_SILENT === 'true',
  },
});
