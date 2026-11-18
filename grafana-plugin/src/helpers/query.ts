export type ParsedQuery<T = string> = Record<string, T | T[] | null>;

// Preserve bare keys, repeated values and omission of undefined used by the API and saved URLs.
export function parseQuery(search: string): ParsedQuery {
  const result: ParsedQuery = Object.create(null);
  for (const part of search
    .trim()
    .replace(/^[?#&]/, '')
    .split('&')) {
    if (!part) {
      continue;
    }
    const [key, value] = new URLSearchParams(`&${part}`).entries().next().value;
    const decoded = part.includes('=') ? value : null;
    result[key] = key in result ? [result[key], decoded].flat() : decoded;
  }
  return result;
}

export function stringifyQuery(query: unknown): string {
  const encode = (value: unknown) =>
    encodeURIComponent(String(value)).replace(
      /[!'()*]/g,
      (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`
    );
  return Object.entries(query ?? {})
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .flatMap(([key, value]) =>
      (Array.isArray(value) ? value : [value])
        .filter((item) => item !== undefined)
        .map((item) => (item === null ? encode(key) : `${encode(key)}=${encode(item)}`))
    )
    .join('&');
}
