// CVE-2026-93687: keep attack strings below the existing character limit.
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { test } = require('node:test');

// Resolve the patched transitive dependency through the actual lint toolchain.
const fromStylelint = createRequire(require.resolve('stylelint'));
const fromMicromatch = createRequire(fromStylelint.resolve('micromatch'));
const braces = fromMicromatch('braces');

for (const [open, close] of [
  ['{', '}'],
  ['(', ')'],
  ['({', '})'],
]) {
  const levels = 4000 / open.length;
  for (const suffix of [close.repeat(levels), '']) {
    const pattern = open.repeat(levels) + 'a,b' + suffix;
    for (const method of ['parse', 'compile', 'expand', 'stringify']) {
      test(`${method} rejects deeply nested ${open} patterns (${suffix ? 'balanced' : 'unclosed'})`, () => {
        assert.ok(pattern.length < 10000);
        assert.throws(() => braces[method](pattern), {
          name: 'SyntaxError',
          message: 'Pattern nesting exceeds 128 levels',
        });
      });
    }
  }
}

test('ordinary lint patterns keep their compile and expansion behavior', () => {
  assert.deepEqual(braces.expand('src/{components,pages}/*.{ts,tsx}'), [
    'src/components/*.ts',
    'src/components/*.tsx',
    'src/pages/*.ts',
    'src/pages/*.tsx',
  ]);
  assert.equal(braces.compile('src/{components,pages}/*.{ts,tsx}'), 'src/(components|pages)/*.(ts|tsx)');
  assert.deepEqual(braces.expand('{1..3}'), ['1', '2', '3']);
});
