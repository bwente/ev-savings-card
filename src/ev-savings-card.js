import { parseTariff, addEnergy } from "./calculations.js";

class EvSavingsCard extends HTMLElement {
  static VERSION = "0.6.3";

  static getStubConfig(hass) {
    const entity = Object.values(hass?.states || {}).find(state => state.attributes?.ev_savings_entry_id);
    return { type: "custom:ev-savings-card", ...(entity ? { integration_entity: entity.entity_id } : {}) };
  }
  static getConfigElement() { return document.createElement("ev-savings-card-editor"); }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {

    this.config = {
      title: "EV Savings",
      default_view: "cost",
      comparison_period: "off_peak",
      decimals: 1,
      currency_decimals: 2,
      include_adjustments: true,
      rate_multiplier: 1,
      rate_addition: 0,
      period_roles: null,
      ...config,
    };

    for (const field of ["decimals", "currency_decimals"]) {
      if (!Number.isInteger(this.config[field]) || this.config[field] < 0 || this.config[field] > 6) throw new Error(`${field} must be an integer from 0 to 6`);
    }
    for (const field of ["rate_multiplier", "rate_addition"]) {
      if (typeof this.config[field] !== "number" || !Number.isFinite(this.config[field])) throw new Error(`${field} must be a finite number`);
    }
    if (!["cost", "savings", "kwh"].includes(this.config.default_view)) throw new Error("Invalid default_view");
    if (!["discount", "off_peak", "peak"].includes(this.config.comparison_period)) throw new Error("Invalid comparison_period");
    new Intl.NumberFormat(undefined, { style: "currency", currency: this.config.currency || "USD" });
    this._requestId = (this._requestId || 0) + 1;
    this.view = this.config.default_view;
    this.monthOffset = 0;
    this._loadedKey = null;
    this._data = null;
    this._loading = false;
    this._error = null;
    this.render();
    if (this._hass) this.loadData();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.config) return;

    const daily = hass.states[this.config.daily_entity];
    const monthly = this.config.monthly_entity
      ? hass.states[this.config.monthly_entity]
      : null;
    const rate = hass.states[this.config.rate_entity];

    const key = [
      daily?.state,
      daily?.last_updated,
      monthly?.state,
      monthly?.last_updated,
      rate?.last_updated,
      hass.states[this.config.integration_entity]?.last_updated,
      this.monthOffset,
      Math.floor(Date.now() / 3600000),
    ].join("|");

    if (key !== this._loadedKey) {
      this._loadedKey = key;
      this.loadData();
    }
  }

  getCardSize() {
    return 8;
  }

  async loadData() {
    if (!this._hass || !this.config) return;

    const requestId = this._requestId = (this._requestId || 0) + 1;
    this._data = null;
    this.selectedDay = null;
    this._error = null;
    this._loading = true;
    this.render();

    try {
      if (this.config.integration_entity) {
        const state = this._hass.states[this.config.integration_entity];
        const entryId = state?.attributes?.ev_savings_entry_id;
        if (!entryId) throw new Error("Choose an EV Savings integration tariff entity.");
        const result = await this._hass.callWS({ type: "ev_savings/month", entry_id: entryId, month_offset: this.monthOffset });
        if (requestId !== this._requestId) return;
        this._data = this.integrationData(result);
        return;
      }
      if (!this.config.daily_entity || !this.config.rate_entity) throw new Error("Choose a daily energy entity and tariff entity in the card editor.");
      const daily = this._hass.states[this.config.daily_entity];
      if (!daily) throw new Error(`Energy entity ${this.config.daily_entity} was not found`);
      if (["unavailable", "unknown"].includes(daily.state)) throw new Error("Energy entity is unavailable");
      if (daily.attributes?.unit_of_measurement !== "kWh") throw new Error("Energy entity must report kWh");
      const zone = this._hass.config?.time_zone;
      if (zone && zone !== Intl.DateTimeFormat().resolvedOptions().timeZone) throw new Error(`Use a browser in the Home Assistant time zone (${zone}) for correct tariff calculations.`);
      const now = new Date();
      const target = new Date(
        now.getFullYear(),
        now.getMonth() + this.monthOffset,
        1
      );
      const start = new Date(target.getFullYear(), target.getMonth(), 1);
      const end = new Date(target.getFullYear(), target.getMonth() + 1, 1);

      // Request one extra hour before the month so the first delta can be calculated.
      const queryStart = new Date(start.getTime() - 60 * 60 * 1000);

      const response = await this._hass.callWS({
        type: "recorder/statistics_during_period",
        start_time: queryStart.toISOString(),
        end_time: end.toISOString(),
        statistic_ids: [this.config.daily_entity],
        period: "hour",
        types: ["sum"],
      });

      const rows = Array.isArray(response)
        ? response
        : response?.[this.config.daily_entity] || [];

      if (requestId !== this._requestId) return;
      this._data = this.buildData(rows, start, end);
      this._error = null;
    } catch (err) {
      if (requestId !== this._requestId) return;
      this._error = String(err?.message || err);
    } finally {
      if (requestId !== this._requestId) return;
      this._loading = false;
      this.render();
    }
  }

  integrationData(result) {
    // These dates are calendar labels only; the backend prices absolute instants.
    const start = new Date(result.year, result.month - 1, 1);
    const end = new Date(result.year, result.month, 1);
    const roles = ["discount", "off_peak", "peak"];
    const periods = roles.map(index => ({ index, effectiveRate: result.tariff.rates[index] }));
    const tariff = { ...result.tariff, periods, names: { discount: "Discount", off_peak: "Off peak", peak: "On peak" },
      discount: { ...periods[0], name: "discount" }, offPeak: { ...periods[1], name: "off peak" }, peak: { ...periods[2], name: "on peak" } };
    const days = new Map(Object.entries(result.days).map(([key, rec]) => [key, { ...rec, date: new Date(`${key}T12:00:00`) }]));
    return { start, end, days, timeZone: result.time_zone, totals: result.totals, warnings: result.warnings, tariff, comparison: result.comparison, costBasis: result.cost_basis, localCharges: result.local_charges, integration: true, isCurrentMonth: this.monthOffset === 0 };
  }

  getTariff() {
    return parseTariff(this.config, this._hass?.states?.[this.config.rate_entity]);
  }

  buildData(rows, start, end) {
    const tariff = this.getTariff();

    const warnings = new Set(["Hourly recorder estimates; recent charging may not appear yet."]);
    const timestamp = value => typeof value === "number" ? new Date(value * (value < 1e12 ? 1000 : 1)) : new Date(value);
    for (const [field, check] of [["startdate", date => date > start], ["enddate", date => date < new Date(Math.min(end.getTime(), Date.now()))]]) {
      const value = tariff[field];
      if (value != null && value !== "") {
        const date = timestamp(typeof value === "string" && /^\d+$/.test(value) ? Number(value) : value);
        if (!Number.isFinite(date.getTime())) throw new Error(`Invalid tariff ${field}`);
        if (check(date)) throw new Error("This tariff does not cover the selected month. Supply the historical tariff version.");
      } else if (field === "startdate") warnings.add("Tariff effective date is missing; historical validity cannot be verified.");
    }
    warnings.add("Tariff refresh and historical versions are managed by the source entity; freshness is not verified by this card.");
    const points = rows
      .filter((r) => r && r.start != null && r.sum != null && r.sum !== "" && Number.isFinite(Number(r.sum)))
      .map((r) => ({
        start: timestamp(r.start),
        sum: Number(r.sum),
      }))
      .filter(r => Number.isFinite(r.start.getTime()))
      .sort((a, b) => a.start - b.start);

    const days = new Map();

    const ensureDay = (date) => {
      const key = this.localDateKey(date);
      if (!days.has(key)) {
        days.set(key, {
          date: new Date(
            date.getFullYear(),
            date.getMonth(),
            date.getDate()
          ),
          kwh: 0,
          actualCost: 0,
          comparisonCost: 0,
          savings: 0,
          discountKwh: 0,
          offPeakKwh: 0,
          peakKwh: 0,
          periodKwh: {},
        });
      }
      return days.get(key);
    };

    let previous = null;

    for (const point of points) {
      if (previous) {
        let delta = point.sum - previous.sum;

        // Long term statistic "sum" is expected to remain monotonic across
        // last_reset events. Ignore invalid negative deltas defensively.
        if (point.start - previous.start !== 3600000 || delta < 0) {
          warnings.add("Missing or corrected recorder statistics: totals are incomplete.");
          previous = point;
          continue;
        }

        const intervalDate = new Date(point.start);

        if (
          intervalDate >= start &&
          intervalDate < end &&
          delta > 0
        ) {
          this.addEnergy(
            ensureDay(intervalDate),
            intervalDate,
            delta,
            tariff
          );
        }
      }

      previous = point;
    }

    const now = new Date();
    const isCurrentMonth = start.getFullYear() === now.getFullYear() && start.getMonth() === now.getMonth();
    if (!points.some(point => point.start >= start && point.start < end)) warnings.add("No recorder statistics for this month. Check that the energy sensor supports long term sum statistics.");
    if (!points.some(point => point.start.getTime() === start.getTime() - 3600000)) warnings.add("Missing opening statistics: the first hour may be excluded.");

    for (const day of days.values()) {
      day.savings = day.comparisonCost - day.actualCost;
    }

    const list = [...days.values()].filter(
      (d) => d.date >= start && d.date < end
    );

    const totals = list.reduce(
      (acc, d) => {
        acc.kwh += d.kwh;
        acc.actualCost += d.actualCost;
        acc.comparisonCost += d.comparisonCost;
        acc.savings += d.savings;
        acc.discountKwh += d.discountKwh;
        acc.offPeakKwh += d.offPeakKwh;
        acc.peakKwh += d.peakKwh;
        return acc;
      },
      {
        kwh: 0,
        actualCost: 0,
        comparisonCost: 0,
        savings: 0,
        discountKwh: 0,
        offPeakKwh: 0,
        peakKwh: 0,
      }
    );

    totals.discountPercent =
      totals.kwh > 0
        ? (totals.discountKwh / totals.kwh) * 100
        : 0;

    return {
      days,
      warnings: [...warnings],
      totals,
      tariff,
      start,
      end,
      isCurrentMonth,
    };
  }

  addEnergy(day, date, kwh, tariff) {
    addEnergy(this.config, day, date, kwh, tariff);
  }

  localDateKey(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  money(value) {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: this.config.integration_entity ? (this._data?.tariff?.currency || "USD") : this.config.currency || "USD",
      minimumFractionDigits: this.config.currency_decimals,
      maximumFractionDigits: this.config.currency_decimals,
    }).format(Number(value || 0));
  }

  number(value, decimals = this.config.decimals) {
    return Number(value || 0).toFixed(decimals);
  }

  rate(value) {
    return `${new Intl.NumberFormat(undefined, { style: "currency", currency: this.config.integration_entity ? (this._data?.tariff?.currency || "USD") : this.config.currency || "USD", minimumFractionDigits: 5, maximumFractionDigits: 5 }).format(value)}/kWh`;
  }

  formatTariffDate(value) {
    if (value === undefined || value === null || value === "") return "";

    const n = Number(value);
    const date = Number.isFinite(n)
      ? new Date(n * 1000)
      : new Date(value);

    if (Number.isNaN(date.getTime())) return "";

    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  setView(view) {
    this.view = view;
    this.render();
  }

  moveMonth(delta) {
    this.monthOffset += delta;
    if (this.monthOffset > 0) this.monthOffset = 0;
    this._loadedKey = null;
    this.loadData();
  }

  render() {
    if (!this.config) return;

    // Read the live disclosure state before replacing the DOM. Keep it while
    // loading too, when the notes element is temporarily absent.
    const notes = this.shadowRoot.querySelector(".data-notes");
    if (notes) this._notesOpen = notes.open;
    const d = this._data;
    const title = this.config.title || "EV Savings";

    this.shadowRoot.innerHTML = `
      <ha-card>
        <style>
          :host { display:block; container-type:inline-size; }
          .wrap { padding: 20px; }
          .top {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:12px;
            flex-wrap:wrap;
          }
          .title {
            font-size:20px;
            font-weight:600;
          }
          .nav {
            display:flex;
            align-items:center;
            gap:4px;
          }
          button {
            font:inherit;
            color:var(--primary-text-color);
            background:transparent;
            border:0;
            border-radius:999px;
            min-width:40px;
            min-height:40px;
            cursor:pointer;
          }
          button:hover {
            background:var(--secondary-background-color);
          }
          button:focus-visible {
            outline:2px solid var(--primary-color);
            outline-offset:2px;
          }
          button[disabled] {
            opacity:.35;
            cursor:default;
          }
          .month {
            min-width:130px;
            text-align:center;
            font-weight:500;
          }
          .summary {
            display:grid;
            grid-template-columns:repeat(3,minmax(0,1fr));
            gap:12px;
            margin:18px 0 10px;
          }
          .metric {
            border-top:1px solid var(--divider-color);
            padding-top:12px;
            min-width:0;
          }
          .metric .label {
            color:var(--secondary-text-color);
            font-size:12px;
            text-transform:uppercase;
            letter-spacing:.04em;
          }
          .metric .value {
            font-size:24px;
            line-height:1.2;
            margin-top:4px;
            font-weight:600;
          }
          .metric.primary .value {
            color:var(--success-color,#2e7d32);
          }
          .reinforce {
            margin:10px 0 16px;
            padding:12px 14px;
            background:color-mix(
              in srgb,
              var(--success-color,#2e7d32) 12%,
              transparent
            );
            border-left:4px solid var(--success-color,#2e7d32);
          }
          .reinforce strong {
            font-size:16px;
          }
          .switcher {
            display:flex;
            justify-content:flex-end;
            gap:4px;
            margin:8px 0 12px;
          }
          .switcher button {
            min-height:34px;
            padding:0 12px;
            min-width:0;
            font-size:13px;
          }
          .switcher button.active {
            background:var(--primary-color);
            color:var(--text-primary-color,white);
          }
          .weekdays,
          .calendar {
            display:grid;
            grid-template-columns:repeat(7,minmax(0,1fr));
            gap:6px;
          }
          .weekday {
            text-align:center;
            color:var(--secondary-text-color);
            font-size:12px;
            padding:6px 0;
          }
          .day {
            min-height:64px;
            border:1px solid var(--divider-color);
            padding:6px;
            box-sizing:border-box;
            background:var(--card-background-color);
          }
          button.day { border-radius:0; text-align:left; display:block; width:100%; color:var(--primary-text-color); }
          .day-details { margin-top:12px; padding:12px; background:var(--secondary-background-color); font-size:12px; }
          .day-details p { color:var(--secondary-text-color); line-height:1.4; }
          .rate-split { display:flex; height:8px; margin-top:10px; gap:2px; }
          .split-discount { background:var(--info-color,#2196f3); }
          .split-off_peak { background:var(--warning-color,#ffc107); }
          .split-peak { background:var(--error-color,#ef5350); }
          .detail-scroll { overflow-x:auto; }
          .day-details table { width:100%; border-collapse:collapse; }
          .day-details th, .day-details td { padding:6px 4px; text-align:right; border-bottom:1px solid var(--divider-color); }
          .day-details th:first-child, .day-details td:first-child { text-align:left; }
          .day.empty {
            border-color:transparent;
            background:transparent;
          }
          .day.has-energy {
            background:color-mix(
              in srgb,
              var(--success-color,#2e7d32) 11%,
              var(--card-background-color)
            );
          }
          .day.negative {
            background:color-mix(
              in srgb,
              var(--warning-color,#f9a825) 14%,
              var(--card-background-color)
            );
          }
          .date {
            font-size:12px;
            color:var(--secondary-text-color);
          }
          .dayval {
            margin-top:7px;
            font-size:14px;
            font-weight:600;
            overflow-wrap:anywhere;
          }
          .unit {
            font-size:10px;
            color:var(--secondary-text-color);
            font-weight:400;
          }
          .rates {
            display:grid;
            grid-template-columns:repeat(3,minmax(0,1fr));
            gap:8px;
            margin-top:14px;
            padding-top:12px;
            border-top:1px solid var(--divider-color);
          }
          .rate-item {
            min-width:0;
          }
          .rate-name {
            color:var(--secondary-text-color);
            font-size:11px;
            text-transform:uppercase;
          }
          .rate-value {
            margin-top:3px;
            font-size:13px;
            font-weight:600;
          }
          .footer {
            margin-top:10px;
            color:var(--secondary-text-color);
            font-size:12px;
            display:flex;
            justify-content:space-between;
            gap:10px;
            flex-wrap:wrap;
          }
          .data-notes { margin-top:8px; font-size:12px; color:var(--secondary-text-color); }
          .data-notes summary { cursor:pointer; }
          .data-notes p { margin:8px 0; line-height:1.45; }
          .error {
            margin-top:16px;
            color:var(--error-color);
            white-space:pre-wrap;
          }
          @container (max-width:520px) {
            .wrap {
              padding:16px 12px;
            }
            .summary { gap:8px; }
            .metric .label { font-size:10px; letter-spacing:0; }
            .rate-value { font-size:11px; overflow-wrap:anywhere; }
            .metric .value {
              font-size:20px;
            }
            .day {
              min-height:55px;
              padding:4px;
            }
            .dayval {
              font-size:12px;
            }
            .weekdays,
            .calendar {
              gap:3px;
            }
          }
          @container (max-width:340px) {
            .summary { grid-template-columns:1fr; gap:4px; }
            .metric { display:flex; align-items:baseline; justify-content:space-between; gap:8px; padding-top:6px; }
            .rates { gap:4px; }
            .dayval { font-size:10px; letter-spacing:-.2px; }
            .rate-name { font-size:9px; }
            .rate-value { font-size:10px; }
          }
        </style>

        <div class="wrap">
          <div class="top">
            <div class="title">${this.escape(title)}</div>
            <div class="nav">
              <button id="prev" type="button" aria-label="Previous month">&#8249;</button>
              <div class="month">${
                d
                  ? this.escape(
                      d.start.toLocaleDateString(undefined, {
                        month: "long",
                        year: "numeric",
                      })
                    )
                  : ""
              }</div>
              <button
                id="next"
                type="button"
                aria-label="Next month"
                ${this.monthOffset >= 0 ? "disabled" : ""}
              >&#8250;</button>
            </div>
          </div>

          ${
            this._loading && !d
              ? `<div style="padding:24px 0;color:var(--secondary-text-color)">Loading charging history...</div>`
              : ""
          }

          ${
            this._error
              ? `<div class="error">${this.escape(this._error)}</div>`
              : ""
          }

          ${d ? this.renderContent(d) : ""}
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector("#prev")?.addEventListener(
      "click",
      () => this.moveMonth(-1)
    );

    this.shadowRoot.querySelector("#next")?.addEventListener(
      "click",
      () => this.moveMonth(1)
    );

    this.shadowRoot.querySelectorAll("[data-day]").forEach(el => {
      el.addEventListener("click", () => {
        const key = el.dataset.day;
        this.selectedDay = this.selectedDay === key ? null : key;
        this.render();
        this.shadowRoot.querySelector(`[data-day="${key}"]`)?.focus();
      });
    });
    this.shadowRoot.querySelectorAll("[data-view]").forEach((el) => {
      el.addEventListener(
        "click",
        () => this.setView(el.dataset.view)
      );
    });
  }

  renderContent(d) {
    const totalKwh =
      d.totals.kwh;

    // Match the message to the displayed precision, including tiny negative deltas.
    const noDisplayedDifference = this.money(Math.abs(d.totals.savings)) === this.money(0);
    const savingsText = noDisplayedDifference
      ? "No difference from the comparison rate"
      : d.totals.savings >= 0
        ? `${this.money(d.totals.savings)} saved by waiting`
        : `${this.money(
            Math.abs(d.totals.savings)
          )} more than the comparison rate`;

    const first = new Date(
      d.start.getFullYear(),
      d.start.getMonth(),
      1
    );

    const lastDay = new Date(
      d.end.getFullYear(),
      d.end.getMonth(),
      0
    ).getDate();

    const cells = [];

    for (let i = 0; i < first.getDay(); i++) {
      cells.push(`<div class="day empty"></div>`);
    }

    for (let dayNum = 1; dayNum <= lastDay; dayNum++) {
      const date = new Date(
        d.start.getFullYear(),
        d.start.getMonth(),
        dayNum
      );

      const rec = d.days.get(this.localDateKey(date));

      let val = "";
      let unit = "";
      let cls = "";

      if (rec && rec.kwh > 0.0001) {
        cls =
          rec.savings < -0.005
            ? "has-energy negative"
            : "has-energy";

        if (this.view === "cost") {
          val = this.money(rec.actualCost);
        } else if (this.view === "kwh") {
          val = this.number(rec.kwh, 2);
          unit = "kWh";
        } else {
          val = this.money(rec.savings);
        }
      }

      cells.push(`
        <${rec ? "button" : "div"}
          ${rec ? `type="button" data-day="${this.localDateKey(date)}" aria-expanded="${this.selectedDay === this.localDateKey(date)}" aria-label="${this.localDateKey(date)} charging details"` : ""}
          class="day ${cls}"
          title="${
            rec
              ? this.escape(this.dayTitle(rec, d.tariff))
              : ""
          }"
        >
          <div class="date">${dayNum}</div>
          ${
            val
              ? `<div class="dayval">${val}${
                  unit
                    ? `<div class="unit">${unit}</div>`
                    : ""
                }</div>`
              : ""
          }
        </${rec ? "button" : "div"}>
      `);
    }

    const comparison =
      (d.comparison || this.config.comparison_period) === "peak"
        ? d.tariff.peak
        : (d.comparison || this.config.comparison_period) === "discount"
        ? d.tariff.discount
        : d.tariff.offPeak;

    const effectiveDate = d.tariff.effective_from || this.formatTariffDate(
      d.tariff.startdate
    );

    const notices = [];
    if (d.warnings.some(w => /incomplete|No usable|No recorder|Missing opening/i.test(w))) notices.push("Incomplete history");
    if (d.warnings.some(w => /unverified|overdue|failed|needs review|need.*review/i.test(w))) notices.push("Check tariff");
    if (d.integration && d.costBasis === "total" && d.localCharges !== "none") notices.push("Local fees unconfirmed");
    const basisLabel = d.integration ? (d.costBasis === "manual" ? "Manual final rates" : d.costBasis === "total" ? "Includes statewide tax & assessment" : "Before additional taxes") : "Hourly estimates";
    return `
      <div class="summary">
        <div class="metric primary">
          <div class="label">${d.integration ? "Estimated cost" : "Total cost"}</div>
          <div class="value">${this.money(
            d.totals.actualCost
          )}</div>
        </div>

        <div class="metric">
          <div class="label">Discount charging</div>
          <div class="value">${this.number(
            d.totals.discountPercent,
            0
          )}%</div>
        </div>

        <div class="metric">
          <div class="label">Energy charged</div>
          <div class="value">
            ${this.number(totalKwh)}
            <span style="font-size:13px;font-weight:400">kWh</span>
          </div>
        </div>
      </div>

      <div class="reinforce">
        <strong>${this.escape(savingsText)}</strong><br>
        <span style="color:var(--secondary-text-color);font-size:13px">
          compared with charging the same energy at
          ${this.escape(
            comparison === d.tariff.peak
              ? "on peak"
              : comparison === d.tariff.discount
              ? "discount"
              : "off peak"
          )}
          rates
        </span>
      </div>

      <div class="switcher" aria-label="Calendar value">
        <button
          type="button"
          aria-pressed="${this.view === "cost"}"
          data-view="cost"
          class="${this.view === "cost" ? "active" : ""}"
        >Cost</button>

        <button
          type="button"
          aria-pressed="${this.view === "savings"}"
          data-view="savings"
          class="${this.view === "savings" ? "active" : ""}"
        >Savings</button>

        <button
          type="button"
          aria-pressed="${this.view === "kwh"}"
          data-view="kwh"
          class="${this.view === "kwh" ? "active" : ""}"
        >kWh</button>
      </div>

      <div class="weekdays">
        ${["S", "M", "T", "W", "T", "F", "S"]
          .map((x) => `<div class="weekday">${x}</div>`)
          .join("")}
      </div>

      <div class="calendar">${cells.join("")}</div>
      ${this.renderDayDetails(d)}

      <div class="rates">
        <div class="rate-item">
          <div class="rate-name">Discount</div>
          <div class="rate-value">${this.rate(
            d.tariff.discount?.effectiveRate
          )}</div>
        </div>

        <div class="rate-item">
          <div class="rate-name">Off peak</div>
          <div class="rate-value">${this.rate(
            d.tariff.offPeak?.effectiveRate
          )}</div>
        </div>

        <div class="rate-item">
          <div class="rate-name">On peak</div>
          <div class="rate-value">${this.rate(
            d.tariff.peak?.effectiveRate
          )}</div>
        </div>
      </div>

      <div class="footer">
        <span>${this.escape(d.tariff.utility)} ${this.escape(d.tariff.name)}${effectiveDate ? ` · ${this.escape(effectiveDate)}` : ""}</span>
        <span>${basisLabel} · v${EvSavingsCard.VERSION}</span>
      </div>
      <details class="data-notes"${this._notesOpen ? " open" : ""}>
        <summary>${notices.length ? this.escape(notices.join(" · ")) : "Rate & data details"}</summary>
        <p>Source: ${this.escape(d.tariff.source)}</p>
        <p>${[...new Set([...d.warnings, d.integration ? d.tariff.scope : ""])].filter(Boolean).map(w => this.escape(w)).join(" ")}</p>
        ${!d.integration ? `<p>${this.config.include_adjustments === false ? "Base energy rates" : "Rates include OpenEI adjustments"} · Multiplier ${this.config.rate_multiplier} · Addition ${this.rate(this.config.rate_addition)}</p>` : ""}
      </details>
    `;
  }

  renderDayDetails(d) {
    const rec = d.days.get(this.selectedDay);
    if (!rec) return "";
    const labels = { discount: "Discount", off_peak: "Off peak", peak: "On peak" };
    const segments = rec.segments || [];
    const time = stamp => new Intl.DateTimeFormat(undefined, { timeZone: d.timeZone, hour: "numeric", minute: "2-digit" }).format(new Date(stamp));
    return `<section class="day-details" aria-label="Charging details">
      <strong>${this.escape(this.selectedDay)} · ${this.number(rec.kwh, 2)} kWh · ${this.money(rec.actualCost)}</strong>
      ${segments.length ? `<div class="rate-split" aria-hidden="true">${segments.map(s => `<span class="split-${s.role}" style="flex:${s.kwh}"></span>`).join("")}</div>
      <p>Hourly charging intervals · ${this.escape(d.timeZone || "local time")}<br>Intervals may include idle time. Sessions crossing midnight appear on both days.</p>
      <div class="detail-scroll"><table><thead><tr><th>Time / rate</th><th>kWh</th><th>Price/kWh</th><th>Cost</th></tr></thead><tbody>${segments.map(s => `<tr><td>${this.escape(time(s.start))}–${this.escape(time(s.end))}<br>${labels[s.role]}</td><td>${this.number(s.kwh,2)}</td><td>${this.rate(s.rate).replace("/kWh", "")}</td><td>${this.money(s.cost)}</td></tr>`).join("")}</tbody></table></div>` : `<p>${this.escape(this.dayTitle(rec, d.tariff))}</p>`}
      <p>Savings versus the selected comparison: ${this.money(rec.savings)}</p>
    </section>`;
  }

  dayTitle(rec, tariff) {
    const parts = [
      `${this.number(rec.kwh)} kWh`,
      `Energy cost ${this.money(rec.actualCost)}`,
      `Savings ${this.money(rec.savings)}`,
    ];

    for (const p of tariff.periods) {
      const kwh = rec.periodKwh[p.index] || 0;
      if (kwh > 0.001) {
        parts.push(
          `${tariff.names[p.index]}: ${this.number(kwh)} kWh`
        );
      }
    }

    return parts.join(" | ");
  }

  escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
}

if (!customElements.get("ev-savings-card")) {
  customElements.define("ev-savings-card", EvSavingsCard);
}

window.customCards = window.customCards || [];

if (
  !window.customCards.some(
    (card) => card.type === "ev-savings-card"
  )
) {
  window.customCards.push({
    type: "ev-savings-card",
    name: "EV Savings Card",
    description:
      "Calendar of EV charging energy cost and time of use savings.",
    preview: false,
  });
}

console.info(
  `%c EV Savings Card %c v${EvSavingsCard.VERSION} `,
  "background:#03a9f4;color:white;font-weight:700;",
  "background:#222;color:white;"
);
