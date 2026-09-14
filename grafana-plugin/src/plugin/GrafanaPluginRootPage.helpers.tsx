export function getQueryParams(): any {
  const searchParams = new URLSearchParams(window.location.search);
  const result: Record<string, string | string[]> = Object.create(null);
  for (const [key, value] of searchParams) {
    if (Object.prototype.hasOwnProperty.call(result, key)) {
      const previous = result[key];
      if (Array.isArray(previous)) {
        previous.push(value);
      } else {
        result[key] = [previous, value];
      }
    } else {
      result[key] = value;
    }
  }
  return result;
}
