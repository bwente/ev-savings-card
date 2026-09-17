"""Graphical onboarding. API credentials stay in the config entry."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from .const import DOMAIN, DUKE_PROFILE
from .openei import fetch, convert
from .manual_flow import ManualFlow


class ConfigFlow(ManualFlow, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()

    async def async_step_user(self, user_input=None):
        if user_input:
            self.selection = user_input
            if user_input["provider"] == "manual":
                return await self.async_step_manual()
            if user_input["provider"] == "openei":
                return await self.async_step_utility()
            return await self.async_step_energy()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("provider", default="manual"): selector.SelectSelector(selector.SelectSelectorConfig(options=[
                {"value": "manual", "label": "Manual rate entry"},
                {"value": DUKE_PROFILE, "label": "Duke Energy Florida RST-1 — utility-verified profile"},
                {"value": "openei", "label": "OpenEI — unverified tariff discovery"}]))}))

    async def async_step_utility(self, user_input=None):
        errors = {}
        if user_input:
            try:
                records = await fetch(async_get_clientsession(self.hass), user_input["api_key"],
                                      ratesforutility=user_input["utility"], sector="Residential")
                self.records = {r["label"]: r for r in records if r.get("energyratestructure") and r.get("label")}
                if not self.records:
                    raise ValueError("No tariffs")
                self.selection.update(user_input)
                return await self.async_step_tariff()
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="utility", errors=errors, data_schema=vol.Schema({
            vol.Required("api_key"): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required("utility"): str}))

    async def async_step_tariff(self, user_input=None):
        errors = {}
        if user_input:
            try:
                roles = {role: user_input[role] for role in ("discount", "off_peak", "peak")}
                version = convert(self.records[user_input["tariff"]], self.hass.config.time_zone, roles)
                self.selection.update({"tariff": user_input["tariff"], "tariff_name": version["name"], "roles": roles, "initial_version": version})
                return await self.async_step_energy()
            except (ValueError, KeyError, TypeError):
                errors["base"] = "unsupported_tariff"
        options = [{"value": k, "label": f'{v["name"]} — {k}'} for k, v in self.records.items()]
        return self.async_show_form(step_id="tariff", errors=errors, data_schema=vol.Schema({
            vol.Required("tariff"): selector.SelectSelector(selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Required("discount", default=2): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
            vol.Required("off_peak", default=1): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
            vol.Required("peak", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=2))}))

    async def async_step_energy(self, user_input=None):
        errors = {}
        if user_input:
            state = self.hass.states.get(user_input["energy_entity"])
            if not state or state.attributes.get("unit_of_measurement") != "kWh" or state.attributes.get("state_class") not in ("total", "total_increasing"):
                errors["base"] = "invalid_energy"
            else:
                self.selection.update(user_input)
                self.selection["cost_basis"] = "total" if self.selection["provider"] == DUKE_PROFILE else "energy"
                self.selection["local_charges"] = "unknown"
                self.selection["time_zone"] = "America/New_York" if self.selection["provider"] == DUKE_PROFILE else self.selection.get("time_zone", self.hass.config.time_zone)
                await self.async_set_unique_id(f'{user_input["energy_entity"]}:{self.selection["provider"]}')
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f'EV Savings — {state.name}', data=self.selection)
        return self.async_show_form(step_id="energy", errors=errors, data_schema=vol.Schema({
            vol.Required("energy_entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="energy")),
            vol.Required("comparison", default="off_peak"): selector.SelectSelector(selector.SelectSelectorConfig(options=["off_peak", "peak", "discount"]))}))


class OptionsFlow(ManualFlow, config_entries.OptionsFlow):
    """Change energy source and comparison without touching tariff history."""

    async def async_step_init(self, user_input=None):
        errors = {}
        config = {**self.config_entry.data, **self.config_entry.options}
        if user_input:
            state = self.hass.states.get(user_input["energy_entity"])
            if not state or state.attributes.get("unit_of_measurement") != "kWh" or state.attributes.get("state_class") not in ("total", "total_increasing"):
                errors["base"] = "invalid_energy"
            else:
                if user_input.pop("update_manual", False):
                    self.manual_update = True
                    self.pending_options = user_input
                    return await self.async_step_manual()
                return self.async_create_entry(title="", data={**self.config_entry.options, **user_input})
        fields = {}
        if config["provider"] == DUKE_PROFILE:
            fields = {
                vol.Required("cost_basis", default=config.get("cost_basis", "energy")): selector.SelectSelector(selector.SelectSelectorConfig(options=[
                    {"value": "total", "label": "Include statewide tax and assessment"},
                    {"value": "energy", "label": "Energy and recovery charges only"}])),
                vol.Required("local_charges", default=config.get("local_charges", "unknown")): selector.SelectSelector(selector.SelectSelectorConfig(options=[
                    {"value": "unknown", "label": "Local charges not yet checked"},
                    {"value": "none", "label": "My bill has no local taxes or franchise fees"}]))}
        return self.async_show_form(step_id="init", errors=errors, data_schema=vol.Schema({
            **fields,
            vol.Optional("update_manual", default=False): bool,
            vol.Required("energy_entity", default=config["energy_entity"]): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="energy")),
            vol.Required("comparison", default=config["comparison"]): selector.SelectSelector(selector.SelectSelectorConfig(options=["off_peak", "peak", "discount"]))}))
