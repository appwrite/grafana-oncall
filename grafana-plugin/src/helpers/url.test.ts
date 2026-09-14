import qs from 'query-string';

import { PLUGIN_ROOT } from './consts';
import { getPathFromQueryParams } from './url';

test('plugin URLs preserve legacy page paths and repeated query parameters', () => {
  const query = { page: 'incident', id: '42', search: 'disk & cpu', team: ['one', 'two'], flag: null };
  const url = getPathFromQueryParams(query);
  expect(url).toBe(`${PLUGIN_ROOT}/incidents/42?flag&search=disk%20%26%20cpu&team=one&team=two`);
  expect(qs.parseUrl(url).query).toEqual({ flag: null, search: 'disk & cpu', team: ['one', 'two'] });
  expect(query.page).toBe('incident');
  expect(query.id).toBe('42');
});

test('query decoding handles Unicode, plus signs and malformed percent sequences', () => {
  expect(qs.parse('name=caf%C3%A9&search=two+words&bad=%ZZ')).toEqual({
    name: 'café',
    search: 'two words',
    bad: '%ZZ',
  });
  // Long runs of incomplete UTF-8 must finish without exponential decoding.
  expect(qs.parse(`value=${'%C2'.repeat(10000)}`).value).toBeDefined();
});
