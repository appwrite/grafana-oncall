module.exports = {
  ...require('./.config/jest.config'),
  testEnvironment: 'jsdom',

  moduleDirectories: ['node_modules', 'src'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'd.ts', 'cjs'],

  moduleNameMapper: {
    'grafana/app/(.*)': '<rootDir>/src/jest/grafanaMock.ts',
    'openapi-fetch': '<rootDir>/src/jest/openapiFetchMock.ts',
    'jest/matchMedia': '<rootDir>/src/jest/matchMedia.ts',
    '^jest$': '<rootDir>/src/jest',
    '^.+\\.(css|scss)$': '<rootDir>/src/jest/styleMock.ts',
    '^lodash-es$': 'lodash',
    '^.+\\.svg$': '<rootDir>/src/jest/svgTransform.ts',
    '^.+\\.png$': '<rootDir>/src/jest/grafanaMock.ts',
  },

  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],

  reporters: process.env.HTML_REPORT_ENABLED
    ? [
        'default',
        [
          'jest-html-reporters',
          {
            openReport: process.env.NODE_ENV !== 'production',
          },
        ],
      ]
    : ['default'],

  testTimeout: 10000,
  testPathIgnorePatterns: ['/node_modules/', '/e2e-tests/'],
  // Grafana 12's CommonJS bundles load a small set of ESM-only dependencies.
  // Let SWC compile those packages for Jest while keeping the rest of
  // node_modules excluded from transforms.
  transformIgnorePatterns: [
    '/node_modules/(?!.*(?:marked|d3-[^/]+|internmap|robust-predicates|react-calendar|get-user-locale|memoize|mimic-function|@wojtekmaj/date-utils|ol(?:/|@)))',
  ],
  transform: {
    '^.+\\.(t|j)sx?$': [
      '@swc/jest',
      {
        sourceMaps: 'inline',
        jsc: {
          parser: {
            syntax: 'typescript',
            tsx: true,
            decorators: true,
            dynamicImport: true,
          },
        },
      },
    ],
  },
};
