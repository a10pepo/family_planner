import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const context = vm.createContext({});
vm.runInContext(readFileSync(new URL('../modules/application/spa.js', import.meta.url), 'utf8'), context);

for (const uri of ['/', '/settings', '/calendar/week', '/calendar/']) {
  test(`SPA route ${uri} serves index`, () => {
    assert.equal(context.handler({ request: { uri, method: 'GET' } }).uri, '/index.html');
  });
}
for (const [uri, method] of [
  ['/api', 'GET'], ['/api/v1/events', 'GET'], ['/api/health', 'GET'],
  ['/assets/missing.js', 'GET'], ['/missing.png', 'GET'], ['/settings', 'POST'],
]) {
  test(`${method} ${uri} preserves origin routing and errors`, () => {
    assert.equal(context.handler({ request: { uri, method } }).uri, uri);
  });
}
test('HEAD navigation is supported', () => {
  assert.equal(context.handler({ request: { uri: '/settings', method: 'HEAD' } }).uri, '/index.html');
});
