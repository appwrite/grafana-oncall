/** @jest-environment ./scripts/jest-fetch-environment.cjs */
import { FaroHelper } from 'helpers/faro';
import { isNetworkError, makeRequest, makeRequestRaw } from './network';

jest.mock('helpers/consts', () => ({ getOnCallApiPath: (path: string) => `/api/oncall${path}` }));
jest.mock('helpers/faro', () => ({
  FaroHelper: {
    pushNetworkRequestEvent: jest.fn(),
    pushFetchNetworkResponseEvent: jest.fn(),
    pushFetchNetworkError: jest.fn(),
    pushNetworkTransportError: jest.fn(),
  },
}));
const fetchMock = jest.fn();
beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = fetchMock;
});

it('sends JSON, repeated query filters, caller headers and explicit credentials', async () => {
  fetchMock.mockResolvedValue(new Response('{"id":1}', { status: 201, headers: { 'x-result': 'ok' } }));
  const result = await makeRequestRaw('/items/?existing=1', {
    method: 'POST',
    params: { team: ['a', 'b'], skip: undefined },
    data: { name: 'test' },
    headers: { 'X-Idempotency-Key': 123 },
    withCredentials: true,
  });
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe('http://localhost/api/oncall/items/?existing=1&team=a&team=b');
  expect(options).toMatchObject({ method: 'POST', body: '{"name":"test"}', credentials: 'include' });
  expect(options.headers.get('Content-Type')).toBe('application/json');
  expect(options.headers.get('X-Idempotency-Key')).toBe('123');
  expect(result).toMatchObject({ data: { id: 1 }, status: 201, headers: { 'x-result': 'ok' } });
});

it('supports empty, non-JSON and JSON string responses', async () => {
  for (const [body, expected, status] of [
    [null, '', 204],
    ['plain text', 'plain text', 200],
    ['"https://login.example"', 'https://login.example', 200],
  ] as const) {
    fetchMock.mockResolvedValueOnce(new Response(body, { status }));
    expect(await makeRequest('/items/')).toBe(expected);
  }
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin', body: undefined });
});

it('retains HTTP error payloads and records failed responses', async () => {
  fetchMock.mockResolvedValue(new Response('{"detail":"Forbidden"}', { status: 403 }));
  const error = await makeRequest('/items/').catch((error) => error);
  expect(isNetworkError(error)).toBe(true);
  expect(error.response).toMatchObject({ status: 403, data: { detail: 'Forbidden' } });
  expect(FaroHelper.pushFetchNetworkError).toHaveBeenCalledTimes(1);
  expect(FaroHelper.pushNetworkTransportError).not.toHaveBeenCalled();
});

it('honors the Slack caller accepting a 403 response', async () => {
  fetchMock.mockResolvedValue(new Response('{"reinstall":true}', { status: 403 }));
  expect(await makeRequest('/slack/', { validateStatus: (status) => status === 200 || status === 403 })).toEqual({
    reinstall: true,
  });
  expect(FaroHelper.pushFetchNetworkError).not.toHaveBeenCalled();
});

it('distinguishes transport failures from HTTP failures', async () => {
  const cause = new TypeError('Failed to fetch');
  fetchMock.mockRejectedValue(cause);
  const error = await makeRequest('/items/').catch((error) => error);
  expect(isNetworkError(error)).toBe(true);
  expect(error.response).toBeUndefined();
  expect(error.cause).toBe(cause);
  expect(FaroHelper.pushNetworkTransportError).toHaveBeenCalledTimes(1);
});

it('forwards the same-origin XSRF token without changing header overrides', async () => {
  document.cookie = 'XSRF-TOKEN=token%2Bvalue';
  fetchMock.mockResolvedValue(new Response('{}'));
  try {
    await makeRequest('/items/', { method: 'POST', data: 'raw', headers: { 'Content-Type': 'text/plain' } });
    const { headers, body } = fetchMock.mock.calls[0][1];
    expect(headers.get('X-XSRF-TOKEN')).toBe('token+value');
    expect(headers.get('Content-Type')).toBe('text/plain');
    expect(body).toBe('raw');
  } finally {
    document.cookie = 'XSRF-TOKEN=; Max-Age=0';
  }
});
