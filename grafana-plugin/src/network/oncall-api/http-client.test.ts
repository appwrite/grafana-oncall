import { Request, Response } from 'node-fetch';

import { FaroHelper } from 'helpers/faro';

import { getCustomFetchFn } from './http-client';

jest.mock('helpers/faro', () => ({
  __esModule: true,

  FaroHelper: {
    initializeFaro: jest.fn(),
    faro: {
      api: {
        pushEvent: jest.fn(),
        pushError: jest.fn(),
      },
    },
    pushFetchNetworkError: jest.fn(),
    pushNetworkRequestEvent: jest.fn(),
    pushFetchNetworkResponseEvent: jest.fn(),
  },
}));

jest.mock('openapi-fetch', () => ({
  __esModule: true,
  default: () => {},
}));

const fetchMock = jest.fn().mockResolvedValue(true);

const HEADERS = new Headers();
HEADERS.set('Content-Type', 'application/json');
const REQUEST_CONFIG = {
  headers: HEADERS,
  body: JSON.stringify({ a: 'a' }),
  method: 'POST',
};
const URL = 'https://someurl.com/';
const SUCCESSFUL_RESPONSE_MOCK = { ok: true };
const FAILING_RESPONSE_MOCK = {
  ok: false,
  json: () => 'ERROR',

  // we need to have clone available to actually clone the response
  clone: () => ({
    ok: false,
    json: () => 'ERROR',
  }),
};
const customFetch = getCustomFetchFn({ withGlobalErrorHandler: true });

describe('customFetch', () => {
  beforeAll(() => {
    Object.defineProperty(global, 'fetch', {
      writable: true,
      value: fetchMock,
    });
  });
  afterEach(jest.resetAllMocks);

  it('passes a Request from openapi-fetch without consuming its body', async () => {
    const createClient = jest.requireActual('../../../node_modules/openapi-fetch/dist/index.cjs').default;
    const client = createClient({ baseUrl: URL, Request, fetch: customFetch });
    fetchMock.mockImplementationOnce(async (request) => {
      expect(request.headers.get('X-Idempotency-Key')).toBeTruthy();
      expect(request.headers.get('Content-Type')).toBe('application/json');
      expect(await request.text()).toBe(REQUEST_CONFIG.body);
      return new Response(JSON.stringify({ id: 'integration' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    });
    const { data } = await client.POST('/alert_receive_channels/', { body: { a: 'a' } });
    expect(data).toEqual({ id: 'integration' });
  });

  describe('if response is successful', () => {
    it('should push event to faro and return response', async () => {
      fetchMock.mockResolvedValue(SUCCESSFUL_RESPONSE_MOCK);
      const response = await customFetch(new Request(URL, REQUEST_CONFIG) as unknown as globalThis.Request);
      expect(FaroHelper.pushNetworkRequestEvent).toHaveBeenCalledWith({
        body: REQUEST_CONFIG.body,
        method: REQUEST_CONFIG.method,
        url: URL,
      });
      expect(response).toEqual(SUCCESSFUL_RESPONSE_MOCK);
    });
  });

  describe('if response is not successful', () => {
    it('should push event and error to faro', async () => {
      fetchMock.mockResolvedValueOnce(FAILING_RESPONSE_MOCK);
      await expect(customFetch(new Request(URL, REQUEST_CONFIG) as unknown as globalThis.Request)).rejects.toEqual(
        FAILING_RESPONSE_MOCK
      );
      expect(FaroHelper.pushNetworkRequestEvent).toHaveBeenCalledWith({
        body: REQUEST_CONFIG.body,
        method: REQUEST_CONFIG.method,
        url: URL,
      });
      expect(FaroHelper.pushFetchNetworkError).toHaveBeenCalledWith({
        method: REQUEST_CONFIG.method,
        responseData: 'ERROR',
        res: FAILING_RESPONSE_MOCK,
      });
    });
  });
});
