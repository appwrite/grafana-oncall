import { getOnCallApiPath } from 'helpers/consts';
import { FaroHelper } from 'helpers/faro';
import { stringifyQuery } from 'helpers/query';
import { safeJSONStringify } from 'helpers/string';

interface RequestConfig {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'OPTIONS';
  params?: unknown;
  data?: unknown;
  withCredentials?: boolean;
  validateStatus?: (status: number) => boolean;
  headers?: Record<string, string | number>;
}

export interface NetworkResponse {
  data: any;
  status: number;
  statusText: string;
  headers: Record<string, string>;
}

export class NetworkError extends Error {
  constructor(
    message: string,
    public response?: NetworkResponse,
    options?: ErrorOptions
  ) {
    super(message, options);
    this.name = 'NetworkError';
  }
}

export const isNetworkError = (error: unknown): error is NetworkError => error instanceof NetworkError;

export async function makeRequestRaw(path: string, config: RequestConfig = {}): Promise<NetworkResponse> {
  const {
    method = 'GET',
    params,
    data,
    headers,
    withCredentials,
    validateStatus = (status) => status >= 200 && status < 300,
  } = config;
  const url = new URL(getOnCallApiPath(path), window.location.href);
  const query = stringifyQuery(params);
  if (query) {
    url.search += `${url.search ? '&' : ''}${query}`;
  }
  const requestHeaders = new Headers({ Accept: 'application/json, text/plain, */*' });
  for (const [key, value] of Object.entries(headers ?? {})) {
    requestHeaders.set(key, String(value));
  }
  // Preserve Axios's same-origin XSRF cookie behavior for Grafana proxy requests.
  const xsrfToken = document.cookie.split('; ').find((cookie) => cookie.startsWith('XSRF-TOKEN='));
  if (url.origin === window.location.origin && xsrfToken) {
    requestHeaders.set('X-XSRF-TOKEN', decodeURIComponent(xsrfToken.slice('XSRF-TOKEN='.length)));
  }
  const body = data === undefined || data === null ? undefined : typeof data === 'string' ? data : JSON.stringify(data);
  if (body !== undefined && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  FaroHelper.pushNetworkRequestEvent({ method, url: url.href, body: `${safeJSONStringify(data)}` });
  try {
    const res = await fetch(url.href, {
      method,
      headers: requestHeaders,
      body,
      credentials: withCredentials ? 'include' : 'same-origin',
    });
    const text = await res.text();
    let responseData: unknown = text;
    try {
      responseData = JSON.parse(text);
    } catch {
      /* Empty and non-JSON responses are valid. */
    }
    const response = {
      data: responseData,
      status: res.status,
      statusText: res.statusText,
      headers: Object.fromEntries(res.headers),
    };
    const accepted = validateStatus(res.status);
    FaroHelper.pushFetchNetworkResponseEvent({ name: accepted ? 'Request succeeded' : 'Request failed', res, method });
    if (!accepted) {
      FaroHelper.pushFetchNetworkError({ res, responseData, method });
      throw new NetworkError(`Request failed with status code ${res.status}`, response);
    }
    return response;
  } catch (error) {
    if (isNetworkError(error)) {
      throw error;
    }
    FaroHelper.pushNetworkTransportError({ method, url: url.href });
    throw new NetworkError('Network request failed', undefined, { cause: error });
  }
}

export async function makeRequest<RT = any>(path: string, config: RequestConfig = {}): Promise<RT> {
  return (await makeRequestRaw(path, config)).data;
}
