"""Tariff status entity used by the dashboard card."""
from datetime import datetime, timezone
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .tariff import version_at, TariffError


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TariffSensor(entry)])


class TariffSensor(SensorEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:ev-station"

    def __init__(self, entry):
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tariff"
        self._attr_name = f"{entry.title} tariff"

    async def async_added_to_hass(self):
        def updated(event):
            if event.data.get("entry_id") == self.entry.entry_id:
                self.async_write_ha_state()
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}_updated", updated))

    @property
    def native_value(self):
        cache = self.entry.runtime_data
        if cache.warning:
            return "needs_review"
        try:
            version = version_at(cache.versions, datetime.now(timezone.utc))
            if version.get("review_after", "9999-12-31") < datetime.now(timezone.utc).date().isoformat():
                return "needs_review"
            return "manual" if version.get("manual") else "verified" if version.get("verified") else "unverified"
        except TariffError:
            return "unavailable"

    @property
    def extra_state_attributes(self):
        cache = self.entry.runtime_data
        return {"ev_savings_entry_id": self.entry.entry_id,
                "energy_entity": self.entry.options.get("energy_entity", self.entry.data["energy_entity"]),
                "time_zone": self.entry.data["time_zone"],
                "provider": self.entry.options.get("provider", self.entry.data["provider"]),
                "last_checked": cache.last_checked, "warning": cache.warning,
                "pending_versions": len(cache.pending)}
