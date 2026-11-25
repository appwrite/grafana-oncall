import { vi } from 'vitest';

import { FaroHelper } from 'helpers/faro';

import { ONCALL_DEV, ONCALL_OPS, ONCALL_PROD } from './consts';

const ErrorMock = vi.spyOn(window, 'Error');

vi.mock('@grafana/faro-web-sdk', async (importOriginal) => {
  const { LogLevel, InternalLoggerLevel } = await importOriginal<typeof import('@grafana/faro-web-sdk')>();
  return {
    initializeFaro: vi.fn().mockReturnValue({
      api: {
        pushLog: vi.fn(),
      },
    }),
    LogLevel,
    InternalLoggerLevel,
    getWebInstrumentations: () => [],
  };
});

vi.mock('@grafana/faro-web-tracing', () => ({
  TracingInstrumentation: vi.fn(),
}));

vi.mock('./consts', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./consts')>()),
  IS_CURRENT_ENV_CLOUD: true,
}));

describe('Faro', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    FaroHelper.faro = undefined;
  });

  test.each([ONCALL_DEV, ONCALL_OPS, ONCALL_PROD])('It initializes faro for environment %s', (onCallApiUrl) => {
    const faro = FaroHelper.initializeFaro(onCallApiUrl);
    expect(faro).toBeDefined();
    expect(ErrorMock).not.toHaveBeenCalled();
  });

  test.each(['https://test.com', 'http://localhost:3000'])(
    'It fails initializing for dummy environment values',
    (onCallApiUrl) => {
      const faro = FaroHelper.initializeFaro(onCallApiUrl);
      expect(faro).toBeUndefined();
    }
  );

  test('It does not reinitialize faro instance if already initialized', () => {
    const instance = FaroHelper.initializeFaro(ONCALL_DEV);
    expect(instance).toBeDefined();

    const result = FaroHelper.initializeFaro(ONCALL_PROD);
    expect(result).toBeUndefined();
    expect(FaroHelper.faro).toBe(instance);
  });

  test('Initializer throws error for wrong env value', () => {
    const faro = FaroHelper.initializeFaro('https://test.com');
    expect(ErrorMock).toHaveBeenCalledWith(`No match found for given onCallApiUrl = https://test.com`);
    expect(faro).toBeUndefined();
  });
});
