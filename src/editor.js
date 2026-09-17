class EvSavingsCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); }
  setConfig(config) { this.config = { ...config }; this.render(); }
  set hass(hass) { this._hass = hass; this.updateSuggestions(); }
  render() {
    if (!this.config) return;
    if (this._controls) { this.syncControls(); this.updateSuggestions(); return; }
    this._controls = new Map();
    this._lists = [];
    const root = this.shadowRoot;
    root.innerHTML = `<style>:host{display:block}label{display:block;margin:12px 0}label[hidden]{display:none}input,select{display:block;box-sizing:border-box;width:100%;padding:10px;font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color)}p{color:var(--secondary-text-color)}</style><p>Select your EV Savings tariff entity. Enter manual prices in Settings → Devices &amp; services → EV Savings → Configure → Enter or update manual rates. Rates, currency and comparison period are managed there. For a new manual plan, add an EV Savings integration and choose Manual rate entry. Legacy settings appear when no integration entity is selected.</p>`;
    const fields = [
      ["title", "Title"], ["integration_entity", "EV Savings integration tariff entity", "entity"], ["daily_entity", "Legacy daily energy entity", "entity"],
      ["rate_entity", "Legacy OpenEI tariff entity", "entity"],
      ["comparison_period", "Comparison period", ["off_peak", "peak", "discount"]],
      ["default_view", "Default calendar view", ["cost", "savings", "kwh"]],
      ["currency", "Currency (for example USD)"]
    ];
    for (const [key, labelText, choices] of fields) {
      const label = document.createElement("label"); label.textContent = labelText;
      const control = document.createElement(Array.isArray(choices) ? "select" : "input");
      if (Array.isArray(choices)) {
        for (const value of choices) { const option = document.createElement("option"); option.value = value; option.textContent = value; control.append(option); }
      } else if (choices === "entity") {
        const list = document.createElement("datalist"); list.id = key;
        this._lists.push(list);
        root.append(list); control.setAttribute("list", key);
      }
      this._controls.set(key, { control, label, fallback: Array.isArray(choices) ? choices[0] : "" });
      control.addEventListener("change", () => {
        const config = { ...this.config };
        if (control.value.trim()) config[key] = control.value.trim(); else delete config[key];
        this.config = config;
        this.syncControls();
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      label.append(control); root.append(label);
    }
    this.syncControls();
    this.updateSuggestions();
  }
  syncControls() {
    const integration = Boolean(this.config.integration_entity);
    for (const [key, { control, label, fallback }] of this._controls) {
      // HA echoes config and state updates while a user may have an uncommitted draft.
      if (this.shadowRoot.activeElement !== control) {
        const value = String(this.config[key] ?? fallback);
        if (control.value !== value) control.value = value;
      }
      label.hidden = integration && ["daily_entity", "rate_entity", "comparison_period", "currency"].includes(key);
    }
  }
  updateSuggestions() {
    if (!this._lists) return;
    const ids = Object.keys(this._hass?.states || {}).filter(id => id.startsWith("sensor.")).sort();
    const signature = JSON.stringify(ids);
    if (signature === this._entitySignature) return;
    this._entitySignature = signature;
    for (const list of this._lists) {
      list.replaceChildren();
      for (const id of ids) {
        const option = document.createElement("option"); option.value = id; list.append(option);
      }
    }
  }
}
if (!customElements.get("ev-savings-card-editor")) customElements.define("ev-savings-card-editor", EvSavingsCardEditor);
