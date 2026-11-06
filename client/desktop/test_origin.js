const test = require('node:test');
const assert = require('node:assert/strict');
const {validate} = require('./origin');

test('accepts local and private Tailscale hosts', () => {
  assert.equal(validate('http://127.0.0.1:3000'), 'http://127.0.0.1:3000');
  assert.equal(validate('hermes.example.ts.net'), 'https://hermes.example.ts.net');
  assert.equal(validate('https://100.100.20.30'), 'https://100.100.20.30');
});

test('rejects public, credentialed, and path-bearing URLs', () => {
  for (const value of ['https://example.com', 'https://user:pass@hermes.example.ts.net',
    'https://hermes.example.ts.net/admin', 'http://hermes.example.ts.net']) {
    assert.throws(() => validate(value));
  }
});
