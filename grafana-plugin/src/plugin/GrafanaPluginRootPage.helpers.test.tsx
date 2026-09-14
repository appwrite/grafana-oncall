import * as runtime from '@grafana/runtime';
import { getGrafanaVersion } from 'helpers/helpers';

import { getQueryParams } from './GrafanaPluginRootPage.helpers';

jest.mock('@grafana/runtime', () => ({
  config: jest.fn(),
}));

describe('GrafanaPluginRootPage.helpers', () => {
  function setGrafanaVersion(version: string) {
    runtime.config.buildInfo = {
      version,
    } as any;
  }

  test('It figures out grafana version from string', () => {
    setGrafanaVersion('10.13.95-9.0.1.1test');

    const { major, minor, patch } = getGrafanaVersion();

    expect(major).toBe(10);
    expect(minor).toBe(13);
    expect(patch).toBe(95);
  });

  test('It figures out grafana version for v9', () => {
    setGrafanaVersion('9.04.3105-rctest100');

    const { major, minor, patch } = getGrafanaVersion();

    expect(major).toBe(9);
    expect(minor).toBe(4);
    expect(patch).toBe(3105);
  });

  test('It figures out grafana version for 1.0.0', () => {
    setGrafanaVersion('1.0.0-any-asd-value');

    const { major, minor, patch } = getGrafanaVersion();

    expect(major).toBe(1);
    expect(minor).toBe(0);
    expect(patch).toBe(0);
  });
});

describe('getQueryParams', () => {
  afterEach(() => window.history.replaceState({}, '', '/'));

  test('represents reserved names as own properties without changing the prototype', () => {
    window.history.replaceState({}, '', '/?__proto__=first&__proto__=second&constructor=value&toString=text');
    const result = getQueryParams();
    expect(Object.getPrototypeOf(result)).toBeNull();
    expect(result.__proto__).toEqual(['first', 'second']);
    expect(result.constructor).toBe('value');
    expect(result.toString).toBe('text');
    expect(Object.prototype).not.toHaveProperty('0');
  });

  test('preserves empty and repeated values', () => {
    window.history.replaceState({}, '', '/?empty=&repeat=&repeat=two&repeat=three&single=one');
    expect(getQueryParams()).toEqual({ empty: '', repeat: ['', 'two', 'three'], single: 'one' });
  });
});
