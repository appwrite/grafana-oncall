import { parseQuery, stringifyQuery } from './query';

it('preserves repeated filters, bare flags, empty values, Unicode and encoded delimiters', () => {
  expect(parseQuery('?team=1&team=2&flag&empty=&q=a+b%26c%3Dd&name=%C3%A9')).toEqual({
    team: ['1', '2'],
    flag: null,
    empty: '',
    q: 'a b&c=d',
    name: 'é',
  });
  expect(
    stringifyQuery({ z: undefined, team: ['1', '2'], flag: null, empty: '', q: 'a b&c=d', name: 'é', none: [] })
  ).toBe('empty=&flag&name=%C3%A9&q=a%20b%26c%3Dd&team=1&team=2');
});

it('round trips values without converting strings to booleans or numbers', () => {
  const query = { active: 'false', id: '001', text: "!'()*~+", repeated: ['x', 'y'] };
  expect(parseQuery(stringifyQuery(query))).toEqual(query);
  expect(stringifyQuery(undefined)).toBe('');
});

it('treats prototype names as ordinary query keys', () => {
  const result = parseQuery('__proto__=one&__proto__=two&constructor=value');
  expect(result.__proto__).toEqual(['one', 'two']);
  expect(Object.getPrototypeOf(result)).toBeNull();
});

it('does not treat question marks inside parameter names as a second query prefix', () => {
  expect(parseQuery('??flag&?another=value')).toEqual({ '?flag': null, '?another': 'value' });
});
