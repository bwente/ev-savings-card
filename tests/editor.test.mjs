import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';

class Node {
  constructor() { this.children = []; this.value = ''; this.listeners = {}; }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  setAttribute() {}
  addEventListener(name, fn) { this.listeners[name] = fn; }
  attachShadow() { this.shadowRoot = new Node(); }
  dispatchEvent(event) { this.lastEvent = event; }
}
const registry = new Map();
const context = vm.createContext({
  HTMLElement: Node, document: { createElement: () => new Node() },
  CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
  customElements: { get: name => registry.get(name), define: (name, value) => registry.set(name, value) }
});
vm.runInContext(await readFile('src/editor.js', 'utf8'), context);
const Editor = registry.get('ev-savings-card-editor');

test('HA updates and configuration echoes preserve focused draft and cursor', () => {
  const editor = new Editor();
  editor.setConfig({ title: 'EV' });
  const input = editor._controls.get('title').control;
  editor.shadowRoot.activeElement = input;
  input.value = 'EV charging'; input.selectionStart = 4; input.selectionEnd = 4;
  const children = [...editor.shadowRoot.children];
  editor.hass = { states: { 'sensor.energy': { state: '10' } } };
  editor.setConfig({ title: 'EV' });
  editor.hass = { states: { 'sensor.energy': { state: '11' }, 'sensor.new': {} } };
  assert.deepEqual(editor.shadowRoot.children, children);
  assert.equal(editor.shadowRoot.activeElement, input);
  assert.equal(input.value, 'EV charging');
  assert.equal(input.selectionStart, 4);
  assert.equal(input.selectionEnd, 4);
  input.listeners.change();
  assert.equal(editor.lastEvent.detail.config.title, 'EV charging');
});

test('integration selection hides ignored settings and preserves legacy config', () => {
  const editor = new Editor();
  editor.setConfig({ daily_entity: 'sensor.energy', comparison_period: 'peak', rate_multiplier: 1.03 });
  const integration = editor._controls.get('integration_entity').control;
  integration.value = 'sensor.ev_tariff'; integration.listeners.change();
  for (const key of ['daily_entity', 'rate_entity', 'comparison_period', 'currency']) {
    assert.equal(editor._controls.get(key).label.hidden, true);
  }
  assert.equal(editor.lastEvent.detail.config.rate_multiplier, 1.03);
  integration.value = ''; integration.listeners.change();
  assert.equal(editor._controls.get('comparison_period').label.hidden, false);
  assert.equal(editor._controls.get('comparison_period').control.value, 'peak');
  assert.equal(editor._controls.get('daily_entity').control.value, 'sensor.energy');
});
