import { vi } from 'vitest';

import { FaroHelper } from 'helpers/faro';
import createClient from 'openapi-fetch';

import { getCustomFetchFn } from './http-client';

vi.mock('helpers/faro', () => ({
  FaroHelper: {
    initializeFaro: vi.fn(),
    faro: {
      api: {
        pushEvent: vi.fn(),
        pushError: vi.fn(),
      },
    },
    pushFetchNetworkError: vi.fn(),
    pushNetworkRequestEvent: vi.fn(),
    pushFetchNetworkResponseEvent: vi.fn(),
  },
}));

const fetchMock = vi.fn().mockResolvedValue(true);

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
  afterEach(vi.resetAllMocks);

  it('passes a Request from openapi-fetch without consuming its body', async () => {
    const client = createClient<{
      '/test': {
        post: {
          requestBody: { content: { 'application/json': { a: string } } };
          responses: { 200: { content: { 'application/json': { id: string } } } };
        };
      };
    }>({ baseUrl: URL, Request, fetch: customFetch });
    fetchMock.mockImplementationOnce(async (request) => {
      expect(request.headers.get('X-Idempotency-Key')).toBeTruthy();
      expect(request.headers.get('Content-Type')).toBe('application/json');
      expect(await request.text()).toBe(REQUEST_CONFIG.body);
      return new Response(JSON.stringify({ id: 'integration' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    });
    const { data } = await client.POST('/test', { body: { a: 'a' } });
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
