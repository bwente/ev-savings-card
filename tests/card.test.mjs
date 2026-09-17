import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { parseTariff, addEnergy } from "../src/calculations.js";
const config = { daily_entity: "sensor.ev", rate_entity: "sensor.tariff", period_roles: { discount: 2, off_peak: 1, peak: 0 }, comparison_period: "off_peak", rate_multiplier: 1, rate_addition: 0 };
const schedule = index => Array.from({ length: 12 }, () => Array(24).fill(index));
const state = () => ({ state: "Example", attributes: { energyratestructure: [[{ rate: .3, adj: .02 }], [{ rate: .2 }], [{ rate: .1 }]], energyweekdayschedule: schedule(2), energyweekendschedule: schedule(0), startdate: 0 } });
const blank = () => ({ kwh: 0, actualCost: 0, comparisonCost: 0, discountKwh: 0, peakKwh: 0, offPeakKwh: 0, periodKwh: {} });
test("explicit zero based mapping, adjustments and delivered rates", () => {
  const tariff = parseTariff({ ...config, rate_multiplier: 2, rate_addition: .01 }, state());
  assert.equal(tariff.discount.index, 2); assert.equal(tariff.peak.index, 0);
  assert.equal(tariff.peak.effectiveRate, .65);
  assert.equal(parseTariff({ ...config, include_adjustments: false }, state()).peak.effectiveRate, .3);
});
test("price inference without friendly names", () => {
  const tariff = parseTariff({ ...config, period_roles: null }, state());
  assert.equal(tariff.discount.index, 2); assert.equal(tariff.offPeak.index, 1);
});
test("reject malformed schedules, tiers, roles and missing prices", () => {
  for (const mutate of [s => s.attributes.energyweekdayschedule[0].pop(), s => s.attributes.energyweekendschedule[0][1] = 4, s => delete s.attributes.energyratestructure[0][0].rate, s => s.attributes.energyratestructure[0].push({ rate: .4 }), s => s.state = "unavailable"]) {
    const s = state(); mutate(s); assert.throws(() => parseTariff(config, s));
  }
  assert.throws(() => parseTariff({ ...config, period_roles: { discount: null } }, state()));
  assert.throws(() => parseTariff({ ...config, period_roles: { discount: 99 } }, state()));
});
test("weekday/weekend costs and savings exclude fixed charges", () => {
  const s = state(); s.attributes.fixedchargefirstmeter = 100;
  const tariff = parseTariff(config, s); const day = blank();
  addEnergy(config, day, new Date(2026, 8, 7, 1), 10, tariff);
  assert.equal(day.actualCost, 1); assert.equal(day.comparisonCost - day.actualCost, 1); assert.equal(day.discountKwh, 10);
  const weekend = blank(); addEnergy(config, weekend, new Date(2026, 8, 6, 1), 10, tariff);
  assert.equal(weekend.actualCost, 3.2); assert.equal(weekend.peakKwh, 10);
});
const registry = new Map();
class Element { attachShadow() { this.shadowRoot = { innerHTML: "", querySelector() { return null; }, querySelectorAll() { return []; } }; } }
const context = vm.createContext({ HTMLElement: Element, customElements: { get: name => registry.get(name), define: (name, element) => registry.set(name, element) }, window: {}, console, Intl, Date });
vm.runInContext(await readFile("dist/ev-savings-card.js", "utf8"), context);
const Card = registry.get("ev-savings-card");
function card() { const c = new Card(); c.setConfig(config); c._hass = { states: { "sensor.tariff": state(), "sensor.ev": { state: "100", attributes: { unit_of_measurement: "kWh" } } } }; return c; }
const start = new Date(2026, 8, 1); const end = new Date(2026, 9, 1);
const row = (hour, sum) => ({ start: new Date(2026, 8, 1, hour).getTime(), sum });
test("picker accepts an empty stub and registers editor", () => { const c = new Card(); assert.doesNotThrow(() => c.setConfig(Card.getStubConfig())); assert.ok(registry.has("ev-savings-card-editor")); });
test("month baseline, millisecond timestamps and no invented live energy", () => {
  const d = card().buildData([row(-1, 100), row(0, 102), row(1, 105)], start, end);
  assert.equal(d.totals.kwh, 5); assert.equal(d.totals.actualCost, .5); assert.equal(d.totals.savings, .5);
});
test("gaps and negative corrections do not become charging", () => {
  const d = card().buildData([row(-1, 100), row(0, 102), row(2, 110), row(3, 109), row(4, 110)], start, end);
  assert.equal(d.totals.kwh, 3); assert.ok(d.warnings.some(w => w.includes("incomplete")));
});
test("null sums cannot become a false zero baseline", () => {
  const d = card().buildData([row(-1, null), row(0, 100)], start, end); assert.equal(d.totals.kwh, 0);
});
test("newer tariff is rejected for historical months", () => {
  const c = card(); c._hass.states[config.rate_entity].attributes.startdate = new Date(2026, 8, 15).getTime() / 1000;
  assert.throws(() => c.buildData([row(-1, 0), row(0, 1)], start, end), /historical tariff/);
});
test("latest request wins when recorder replies arrive out of order", async () => {
  const c = card(); const pending = []; c._hass.callWS = () => new Promise(resolve => pending.push(resolve));
  const first = c.loadData(); c.monthOffset = -1; const second = c.loadData();
  pending[1]({ [config.daily_entity]: [] }); await second; const selected = c._data.start.getTime();
  pending[0]({ [config.daily_entity]: [] }); await first; assert.equal(c._data.start.getTime(), selected);
});
test("missing energy entity reports an error and hides old totals", async () => {
  const c = card(); delete c._hass.states[config.daily_entity]; await c.loadData(); assert.match(c._error, /not found/); assert.equal(c._data, null);
});
test("tariff source is visible and entity text is escaped", () => {
  const c = card(); c._hass.states[config.rate_entity].attributes.source = '<img src=x onerror=alert(1)>';
  const data = c.buildData([row(-1, 0), row(0, 1)], start, end);
  const html = c.renderContent(data); assert.ok(html.includes('Source: &lt;img')); assert.ok(!html.includes('<img'));
});
test("release versions and bundled card agree with the distribution", async () => {
  const pkg = JSON.parse(await readFile('package.json')); const hacs = JSON.parse(await readFile('hacs.json'));
  const manifest = JSON.parse(await readFile('custom_components/ev_savings/manifest.json'));
  assert.equal(Card.VERSION, pkg.version); assert.equal(manifest.version, pkg.version); assert.equal(hacs.filename, undefined);
  assert.equal(await readFile('dist/ev-savings-card.js', 'utf8'), await readFile('custom_components/ev_savings/www/ev-savings-card.js', 'utf8'));
});

test("seasonal schedule selects the consumption month at exact hour boundaries", () => {
  const s = state();
  // Synthetic seasonal prices; these are not Duke's current delivered rates.
  s.attributes.energyweekdayschedule = Array.from({ length: 12 }, (_, month) =>
    Array.from({ length: 24 }, (_, hour) => {
      const winter = [11, 0, 1].includes(month);
      if (hour < (winter ? 3 : 6)) return 2;
      if ((winter && hour >= 5 && hour < 10) || (hour >= 18 && hour < 21)) return 0;
      return 1;
    }));
  const tariff = parseTariff(config, s);
  for (const [date, index] of [
    [new Date(2026, 1, 2, 2), 2], [new Date(2026, 1, 2, 3), 1],
    [new Date(2026, 1, 2, 5), 0], [new Date(2026, 1, 2, 10), 1],
    [new Date(2026, 2, 2, 5), 2], [new Date(2026, 2, 2, 6), 1],
    [new Date(2026, 10, 30, 5), 2], [new Date(2026, 11, 1, 5), 0],
    [new Date(2026, 11, 1, 18), 0], [new Date(2026, 11, 1, 21), 1]
  ]) {
    const day = blank(); addEnergy(config, day, date, 10, tariff);
    assert.equal(day.periodKwh[index], 10, date.toString());
    assert.ok(Math.abs(day.actualCost - 10 * tariff.periods[index].effectiveRate) < 1e-9);
    assert.ok(Math.abs(day.comparisonCost - 2) < 1e-9);
  }
});

test("New York DST counts 23 spring hours and 25 fall hours without gaps or duplication", () => {
  const oldZone = process.env.TZ;
  process.env.TZ = "America/New_York";
  try {
    for (const [month, day, hours] of [[2, 8, 23], [10, 1, 25]]) {
      const c = card();
      const s = c._hass.states[config.rate_entity];
      s.attributes.energyweekendschedule = schedule(1);
      s.attributes.energyweekendschedule[month][1] = 2;
      const from = new Date(2026, month, day);
      const to = new Date(2026, month, day + 1);
      const rows = Array.from({ length: hours + 1 }, (_, i) => ({ start: from.getTime() + (i - 1) * 3600000, sum: 100 + i }));
      assert.equal((to - from) / 3600000, hours);
      const d = c.buildData(rows, from, to);
      assert.equal(d.totals.kwh, hours);
      assert.equal(d.days.size, 1);
      assert.equal(d.totals.discountKwh, hours === 25 ? 2 : 1);
      assert.ok(!d.warnings.some(w => w.includes("corrected")));
    }
  } finally {
    if (oldZone === undefined) delete process.env.TZ; else process.env.TZ = oldZone;
  }
});

test("integration mode requests backend accounting and preserves service calendar dates", async () => {
  const c = card();
  c.config.integration_entity = 'sensor.ev_backend';
  c._hass.states.sensor = undefined;
  c._hass.states['sensor.ev_backend'] = { attributes: { ev_savings_entry_id: 'entry' } };
  const result = { year: 2026, month: 9, days: { '2026-09-11': { kwh: 45.4288286908208, actualCost:4.66, comparisonCost:6.26, savings:1.60, discountKwh:45.4288286908208, offPeakKwh:0, peakKwh:0, periodKwh:{discount:45.4288286908208} } },
    totals:{kwh:45.4288286908208,actualCost:4.66,savings:1.60,discountPercent:100}, warnings:['Pre-tax only'], comparison:'peak',
    tariff:{rates:{discount:.10256,off_peak:.13776,peak:.17218},source:'Duke sheets',utility:'Duke',name:'RST-1',effective_from:'2026-09-01',scope:'Pre-tax only'} };
  c._hass.callWS = async request => { assert.equal(request.type, 'ev_savings/month'); assert.equal(request.entry_id,'entry'); return result; };
  await c.loadData();
  assert.equal(c._error, null); assert.equal(c._data.start.getMonth(), 8);
  assert.equal(c._data.days.get('2026-09-11').kwh,45.4288286908208);
  const html = c.renderContent(c._data);
  assert.match(html,/Duke sheets/); assert.match(html,/2026-09-01/);
  assert.ok(!html.includes('Rates include OpenEI adjustments'));
});

test("comparison message handles zero and small positive or negative differences", () => {
  const c = card();
  const d = c.buildData([row(-1, 0), row(0, 1)], start, end);
  for (const savings of [0, -1e-12, 1e-12, -.004, .004]) {
    d.totals.savings = savings;
    const html = c.renderContent(d);
    assert.match(html, /No difference from the comparison rate/);
    assert.ok(!html.includes('more than the comparison rate'));
    assert.ok(!html.includes('saved by waiting'));
  }
  d.totals.savings = -.01;
  assert.match(c.renderContent(d), /\$0.01 more than the comparison rate/);
  d.totals.savings = .01;
  assert.match(c.renderContent(d), /\$0.01 saved by waiting/);
});

test("compact card collapses source details and keeps incomplete-history notice visible", () => {
  const c = card();
  const d = c.buildData([row(-1, 0), row(0, 1)], start, end);
  d.warnings = ['Recorder coverage is incomplete: 258 of 260 completed hours.'];
  const html = c.renderContent(d);
  assert.match(html, /<summary>Incomplete history<\/summary>/);
  assert.ok(!/<details[^>]*\bopen\b/.test(html));
  assert.equal((html.match(/Source:/g)||[]).length,1);
});

test("day details expose both rate portions and accessible day controls", () => {
  const c=card();
  const d=c.integrationData({year:2026,month:9,time_zone:'America/New_York',comparison:'off_peak',cost_basis:'manual',
    days:{'2026-09-11':{kwh:20,actualCost:2.502,savings:.354,periodKwh:{discount:10,off_peak:10},segments:[
      {start:'2026-09-11T09:00:00Z',end:'2026-09-11T10:00:00Z',role:'discount',rate:.1074,kwh:10,cost:1.074},
      {start:'2026-09-11T10:00:00Z',end:'2026-09-11T11:00:00Z',role:'off_peak',rate:.1428,kwh:10,cost:1.428}]}},
    totals:{kwh:20,actualCost:2.502,savings:.354,discountPercent:50},warnings:[],
    tariff:{currency:'USD',rates:{discount:.1074,off_peak:.1428,peak:.1779},name:'Manual',utility:'Example',source:'Manual entry',scope:'Entered prices'}});
  c.selectedDay='2026-09-11';
  const html=c.renderContent(d);
  assert.match(html,/data-day="2026-09-11" aria-expanded="true"/);
  assert.match(html,/Hourly charging intervals/);
  assert.match(html,/\$1.07/);assert.match(html,/\$1.43/);
  assert.match(html,/split-discount/);assert.match(html,/split-off_peak/);
});
