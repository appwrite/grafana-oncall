import { existsSync } from 'node:fs';
import { access, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { defineConfig, type RsbuildPlugin } from '@rsbuild/core';
import { pluginReact } from '@rsbuild/plugin-react';

import packageJson from './package.json';
import pluginJson from './src/plugin.json';

const sourceDir = path.resolve(import.meta.dirname, 'src');
const distDir = path.resolve(import.meta.dirname, 'dist');
const readmePath = existsSync(path.join(sourceDir, 'README.md'))
  ? path.join(sourceDir, 'README.md')
  : path.resolve(import.meta.dirname, '../README.md');

const grafanaExternals = [
  'lodash',
  'jquery',
  'moment',
  'slate',
  'emotion',
  '@emotion/react',
  '@emotion/css',
  'prismjs',
  'slate-plain-serializer',
  '@grafana/slate-react',
  'react',
  'react-dom',
  'react-redux',
  'redux',
  'rxjs',
  'react-router',
  'react-router-dom',
  'd3',
  'angular',
  '@grafana/ui',
  '@grafana/runtime',
  '@grafana/data',
];

const replacePluginMetadata = (): RsbuildPlugin => ({
  name: 'replace-plugin-metadata',
  setup(api) {
    api.onAfterBuild(async () => {
      const replacements = [
        [/%VERSION%/g, packageJson.version],
        [/%TODAY%/g, new Date().toISOString().substring(0, 10)],
        [/%PLUGIN_ID%/g, pluginJson.id],
      ] as const;

      await Promise.all(
        ['plugin.json', 'README.md'].map(async (filename) => {
          const outputPath = path.join(distDir, filename);

          try {
            await access(outputPath);
          } catch {
            return;
          }

          const contents = await readFile(outputPath, 'utf8');
          const replaced = replacements.reduce(
            (result, [search, replacement]) => result.replace(search, replacement),
            contents
          );
          await writeFile(outputPath, replaced);
        })
      );
    });
  },
});

export default defineConfig(({ envMode }) => {
  const isProduction = envMode === 'production';

  return {
    plugins: [
      pluginReact({
        // Grafana provides React to plugins through AMD. The automatic JSX
        // runtime would bundle react/jsx-runtime and mix it with that host copy.
        swcReactOptions: { runtime: 'classic' },
      }),
      replacePluginMetadata(),
    ],
    source: {
      decorators: {
        version: 'legacy',
      },
      define: {
        // Preserve the environment contract from the previous Webpack build.
        'process.env.NODE_ENV': JSON.stringify('development'),
        'process.env.PLUGIN_ID': JSON.stringify(pluginJson.id),
      },
      entry: {
        module: './src/module.ts',
      },
    },
    output: {
      assetPrefix: `public/plugins/${pluginJson.id}/`,
      cleanDistPath: false,
      copy: [
        {
          context: sourceDir,
          from: '**/*.{json,svg,png,html}',
          noErrorOnMissing: true,
          to: '[path][name][ext]',
        },
        {
          from: readmePath,
          to: 'README.md',
          toType: 'file',
        },
        {
          from: path.resolve(import.meta.dirname, '../LICENSE'),
          to: 'LICENSE',
          toType: 'file',
        },
        {
          from: path.resolve(import.meta.dirname, '../CHANGELOG.md'),
          noErrorOnMissing: true,
          to: 'CHANGELOG.md',
          toType: 'file',
        },
      ],
      dataUriLimit: 0,
      distPath: {
        root: distDir,
        font: 'fonts',
        image: 'img',
        js: '',
        svg: 'img',
      },
      filename: {
        font: isProduction ? '[contenthash][ext]' : '[name][ext]',
        image: isProduction ? '[contenthash][ext]' : '[name][ext]',
        js: '[name].js',
        svg: isProduction ? '[contenthash][ext]' : '[name][ext]',
      },
      filenameHash: false,
      sourceMap: {
        js: isProduction ? 'source-map' : 'eval-source-map',
      },
    },
    performance: {
      chunkSplit: {
        strategy: 'all-in-one',
      },
    },
    server: {
      publicDir: false,
    },
    tools: {
      htmlPlugin: false,
      rspack(config) {
        config.externals = [
          ...grafanaExternals,
          ({ request }, callback) => {
            const legacyPrefix = 'grafana/';
            callback(undefined, request?.startsWith(legacyPrefix) ? request.slice(legacyPrefix.length) : undefined);
          },
        ];
        config.output = {
          ...config.output,
          clean: {
            keep: /(.*?_(amd64|arm(64)?)(\.exe)?|go_plugin_build_manifest)/,
          },
          library: {
            type: 'amd',
          },
          uniqueName: pluginJson.id,
        };
        config.resolve ??= {};
        config.resolve.modules = [sourceDir, 'node_modules'];
        config.module ??= {};
        config.module.parser = {
          ...config.module.parser,
          javascript: {
            ...config.module.parser?.javascript,
            exportsPresence: 'warn',
          },
        };
        config.watchOptions = {
          ...config.watchOptions,
          ignored: ['**/node_modules/', '**/dist'],
        };
        return config;
      },
      swc(config) {
        config.jsc ??= {};
        config.jsc.transform = {
          ...config.jsc.transform,
          decoratorMetadata: false,
        };
        return config;
      },
    },
  };
});
